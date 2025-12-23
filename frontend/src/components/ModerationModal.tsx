import { useState, useEffect } from 'react';
import { useSocketStore } from '../stores/socketStore';
import { useActionStore } from '../stores/actionStore';
import { useGameStore } from '../stores/gameStore';
import { useAuthStore } from '../stores/authStore';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface Action {
  id: number;
  player_id: number;
  character_name: string;
  action_text: string;
  order: number;
}

interface ModerationModalProps {
  isOpen: boolean;
  onClose: () => void;
  hostUserId?: number;
}

// NOTE: This modal is only accessible to the host player
// Non-host players cannot see the action queue or action text
// until the judgment phase begins (Requirements 1.3, 1.4)

// Sortable Action Item Component
interface SortableActionItemProps {
  action: Action;
  isEditing: boolean;
  editText: string;
  editError: string | null;
  onEdit: (action: Action) => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onDelete: (actionId: number) => void;
  onEditTextChange: (text: string) => void;
  isDragDisabled: boolean;
  isHostAction: boolean;
}

function SortableActionItem({
  action,
  isEditing,
  editText,
  editError,
  onEdit,
  onSaveEdit,
  onCancelEdit,
  onDelete,
  onEditTextChange,
  isDragDisabled,
  isHostAction,
}: SortableActionItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: action.id, disabled: isDragDisabled });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-white p-4 rounded-lg border transition-colors shadow-sm ${
        isHostAction 
          ? 'border-yellow-400 border-2 hover:border-yellow-500' 
          : 'border-slate-200 hover:border-slate-300'
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center gap-2 flex-1">
          {/* Drag handle - only show when not editing and more than one action */}
          {!isDragDisabled && !isEditing && (
            <div
              {...attributes}
              {...listeners}
              className="cursor-grab active:cursor-grabbing text-slate-400 hover:text-slate-600 p-1"
              title="순서 변경하려면 드래그"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </div>
          )}
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="text-sm font-semibold text-blue-600">
                {action.character_name}
              </div>
              {isHostAction && (
                <span className="bg-yellow-400 text-slate-900 text-xs font-bold px-2 py-0.5 rounded">
                  호스트
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500">
              플레이어 ID: {action.player_id}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <button
                onClick={onSaveEdit}
                disabled={!editText.trim()}
                className="text-green-600 hover:text-green-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                저장
              </button>
              <button
                onClick={onCancelEdit}
                className="text-slate-600 hover:text-slate-700 text-sm font-medium"
              >
                취소
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => onEdit(action)}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                수정
              </button>
              <button
                onClick={() => onDelete(action.id)}
                className="text-red-600 hover:text-red-700 text-sm font-medium"
              >
                삭제
              </button>
            </>
          )}
        </div>
      </div>

      {isEditing ? (
        <div>
          <textarea
            value={editText}
            onChange={(e) => onEditTextChange(e.target.value)}
            className={`w-full bg-slate-50 text-slate-900 p-2 rounded text-sm border focus:outline-none ${
              editError ? 'border-red-500 focus:border-red-400' : 'border-slate-200 focus:border-blue-500'
            }`}
            rows={3}
            autoFocus
          />
          {editError && (
            <div className="text-red-600 text-xs mt-1">
              {editError}
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-slate-700 mt-2">
          {action.action_text}
        </div>
      )}
    </div>
  );
}

export default function ModerationModal({ isOpen, onClose, hostUserId }: ModerationModalProps) {
  const [actions, setActions] = useState<Action[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [queueLoadError, setQueueLoadError] = useState<boolean>(false);
  const [editError, setEditError] = useState<string | null>(null);
  
  const currentSession = useGameStore((state) => state.currentSession);
  const emit = useSocketStore((state) => state.emit);
  const on = useSocketStore((state) => state.on);
  const off = useSocketStore((state) => state.off);
  const queueCount = useActionStore((state) => state.queueCount);
  const userId = useAuthStore((state) => state.userId);
  
  // Get current user ID for host badge display
  const currentUserId = hostUserId || userId || 1;

  // Set up drag-and-drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
  
  // Emit get_queue event when modal opens
  useEffect(() => {
    if (isOpen && currentSession) {
      setQueueLoadError(false);
      setErrorMessage(null);
      emit('get_queue', { session_id: currentSession.id });
    }
  }, [isOpen, currentSession, emit]);
  
  // Retry loading queue
  const handleRetryLoadQueue = () => {
    if (currentSession) {
      setQueueLoadError(false);
      setErrorMessage(null);
      emit('get_queue', { session_id: currentSession.id });
    }
  };
  
  // Listen for queue_data event
  useEffect(() => {
    const handleQueueData = (data: { actions: Action[] }) => {
      setActions(data.actions);
    };
    
    on('queue_data', handleQueueData);
    
    return () => {
      off('queue_data', handleQueueData);
    };
  }, [on, off]);
  
  // Listen for queue_updated event
  useEffect(() => {
    const handleQueueUpdated = (data: { actions: Action[] }) => {
      setActions(data.actions);
    };
    
    on('queue_updated', handleQueueUpdated);
    
    return () => {
      off('queue_updated', handleQueueUpdated);
    };
  }, [on, off]);
  
  // Listen for error events
  useEffect(() => {
    const handleError = (data: { message: string }) => {
      console.error('Modal error:', data.message);
      
      // Determine error type based on message content
      if (data.message.includes('retrieve queue') || data.message.includes('Failed to retrieve')) {
        setQueueLoadError(true);
        setErrorMessage(data.message);
      } else if (data.message.includes('edit') || data.message.includes('empty')) {
        setEditError(data.message);
        // Clear edit error after 5 seconds
        setTimeout(() => setEditError(null), 5000);
      } else if (data.message.includes('delete')) {
        setErrorMessage(data.message);
        // Clear error after 5 seconds
        setTimeout(() => setErrorMessage(null), 5000);
      } else if (data.message.includes('commit')) {
        setErrorMessage(data.message);
        // Clear error after 5 seconds
        setTimeout(() => setErrorMessage(null), 5000);
      } else {
        // Generic error
        setErrorMessage(data.message);
        setTimeout(() => setErrorMessage(null), 5000);
      }
    };
    
    on('error', handleError);
    
    return () => {
      off('error', handleError);
    };
  }, [on, off]);

  // Handle drag end - reorder actions
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (!over || active.id === over.id) {
      return;
    }

    setActions((items) => {
      const oldIndex = items.findIndex((item) => item.id === active.id);
      const newIndex = items.findIndex((item) => item.id === over.id);

      // Optimistically update local state
      const reordered = arrayMove(items, oldIndex, newIndex);

      // Emit reorder_actions event to backend
      if (currentSession && userId) {
        const actionIds = reordered.map((action) => action.id);
        emit('reorder_actions', {
          session_id: currentSession.id,
          action_ids: actionIds,
          user_id: userId,
        });
      }

      return reordered;
    });
  };

  // Handle edit mode activation
  const handleEdit = (action: Action) => {
    setEditingId(action.id);
    setEditText(action.action_text);
  };

  // Handle save edit with validation
  const handleSaveEdit = () => {
    // Clear previous edit errors
    setEditError(null);
    
    // Validate text is non-empty
    if (!editText.trim()) {
      setEditError('Action text cannot be empty');
      return;
    }
    
    if (!currentSession || !userId) return;
    
    emit('edit_action', {
      session_id: currentSession.id,
      action_id: editingId,
      new_text: editText,
      user_id: userId,
    });
    
    setEditingId(null);
    setEditText('');
  };

  // Handle cancel edit - revert changes
  const handleCancelEdit = () => {
    setEditingId(null);
    setEditText('');
    setEditError(null);
  };

  // Handle delete with confirmation dialog
  const handleDelete = (actionId: number) => {
    if (!currentSession || !userId) return;
    
    // Show confirmation dialog
    if (!confirm('이 행동을 삭제하시겠습니까?')) {
      return;
    }
    
    // Emit delete_action event
    emit('delete_action', {
      session_id: currentSession.id,
      action_id: actionId,
      user_id: userId,
    });
  };

  // Handle commit - validate and emit commit_actions event
  const handleCommit = () => {
    // Validate actions array is non-empty
    if (!currentSession || actions.length === 0 || !userId) return;
    
    // Emit commit_actions event
    emit('commit_actions', {
      session_id: currentSession.id,
      user_id: userId,
    });
    
    // Close modal on successful commit
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col shadow-card">
        {/* Header with queue count */}
        <div className="flex justify-between items-center mb-4 pb-4 border-b border-slate-200">
          <h2 className="text-xl font-bold text-slate-800">
            행동 결정 ({queueCount}개 제출 됨)
          </h2>
          <button 
            onClick={onClose} 
            className="text-slate-400 hover:text-slate-600 text-2xl leading-none"
            aria-label="모달 닫기"
          >
            ✕
          </button>
        </div>

        {/* Error toast for general errors */}
        {errorMessage && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg relative">
            <div className="flex justify-between items-start">
              <span className="text-sm">{errorMessage}</span>
              <button
                onClick={() => setErrorMessage(null)}
                className="text-red-600 hover:text-red-700 ml-4"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Content area - scrollable */}
        <div className="flex-1 overflow-y-auto mb-4 bg-slate-50 rounded-lg p-4">
          {queueLoadError ? (
            <div className="text-center py-8">
              <div className="text-red-600 mb-4">
                행동 대기열을 불러오지 못했습니다
              </div>
              <button
                onClick={handleRetryLoadQueue}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm shadow-sm"
              >
                다시 시도
              </button>
            </div>
          ) : actions.length === 0 ? (
            <div className="text-center text-slate-400 py-8">
              대기 중인 행동이 없습니다
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={actions.map((a) => a.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-3">
                  {actions.map((action) => (
                    <SortableActionItem
                      key={action.id}
                      action={action}
                      isEditing={editingId === action.id}
                      editText={editText}
                      editError={editingId === action.id ? editError : null}
                      onEdit={handleEdit}
                      onSaveEdit={handleSaveEdit}
                      onCancelEdit={handleCancelEdit}
                      onDelete={handleDelete}
                      onEditTextChange={setEditText}
                      isDragDisabled={actions.length <= 1}
                      isHostAction={action.player_id === currentUserId}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </div>

        {/* Footer with buttons */}
        <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg transition-colors border border-slate-300 font-medium"
          >
            닫기
          </button>
          <button
            onClick={handleCommit}
            disabled={actions.length === 0}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm font-medium"
          >
            제출하기
          </button>
        </div>
      </div>
    </div>
  );
}
