import { useState, useEffect } from 'react';
import { useAuthStore } from '../stores/authStore';
import { useGameStore } from '../stores/gameStore';
import type {
  Character as BaseCharacter,
  Skill as BaseSkill,
  AbilityKey,
  InventoryItem,
  InventoryItemType,
  Weakness,
  UnifiedStatus,
} from '../types/character';
import { ABILITY_LABELS, ABILITY_SHORT_LABELS } from '../types/character';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface Skill extends BaseSkill {
  type: 'passive' | 'active';
  description: string;
}

interface EditableStatus {
  name: string;
  type: 'buff' | 'debuff';
  modifier: number;
}

interface EditableInventoryItem extends InventoryItem {
  name: string;
  type: InventoryItemType;
  quantity: number;
}

interface Character {
  id: number;
  user_id: number;
  name: string;
  data: {
    age?: number;
    race?: string;
    concept?: string;
    strength: number;
    dexterity: number;
    constitution: number;
    intelligence: number;
    wisdom: number;
    charisma: number;
    skills: Skill[];
    weaknesses: (string | Weakness)[];
    statuses?: UnifiedStatus[];
    status_effects: string[];
    inventory: (string | InventoryItem)[];
    HP: number;
    MP: number;
  };
  created_at: string;
}

interface CharacterManagementProps {
  onSelectCharacter: (character: BaseCharacter & { user_id: number; created_at: string }) => void;
}

export default function CharacterManagement({ onSelectCharacter }: CharacterManagementProps) {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);
  
  // Form state
  const [name, setName] = useState('');
  const [age, setAge] = useState(25);
  const [race, setRace] = useState('인간');
  const [concept, setConcept] = useState('');
  
  // D20 Ability Scores
  const [strength, setStrength] = useState(10);
  const [dexterity, setDexterity] = useState(10);
  const [constitution, setConstitution] = useState(10);
  const [intelligence, setIntelligence] = useState(10);
  const [wisdom, setWisdom] = useState(10);
  const [charisma, setCharisma] = useState(10);
  
  // Skills
  const [skills, setSkills] = useState<Skill[]>([]);
  const [newSkillType, setNewSkillType] = useState<'passive' | 'active'>('passive');
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillDescription, setNewSkillDescription] = useState('');
  const [newSkillAbility, setNewSkillAbility] = useState<AbilityKey | ''>('');
  
  const [statuses, setStatuses] = useState<EditableStatus[]>([]);
  const [newStatusName, setNewStatusName] = useState('');
  const [newStatusType, setNewStatusType] = useState<'buff' | 'debuff'>('debuff');
  const [newStatusModifier, setNewStatusModifier] = useState(-1);

  const [inventory, setInventory] = useState<EditableInventoryItem[]>([]);
  const [newItemName, setNewItemName] = useState('');
  const [newItemType, setNewItemType] = useState<InventoryItemType>('equipment');
  const [newItemQuantity, setNewItemQuantity] = useState(1);
  const [newItemEquipped, setNewItemEquipped] = useState(false);
  const [newItemModifier, setNewItemModifier] = useState(0);
  const [newItemDescription, setNewItemDescription] = useState('');
  
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [duplicatingCharacterId, setDuplicatingCharacterId] = useState<number | null>(null);
  const [shareCodeInput, setShareCodeInput] = useState('');
  const [latestShareCode, setLatestShareCode] = useState<{ characterName: string; code: string } | null>(null);
  const [sharingCharacterId, setSharingCharacterId] = useState<number | null>(null);
  const [redeemingShareCode, setRedeemingShareCode] = useState(false);
  const [consumingItemKey, setConsumingItemKey] = useState<string | null>(null);
  
  const userId = useAuthStore((state) => state.userId);
  const username = useAuthStore((state) => state.username);
  const logout = useAuthStore((state) => state.logout);
  const currentCharacter = useGameStore((state) => state.currentCharacter);

  useEffect(() => {
    loadCharacters();
  }, [userId]);

  const loadCharacters = async () => {
    if (!userId) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/characters/user/${userId}`);
      if (response.ok) {
        const data = await response.json();
        setCharacters(data);
      }
    } catch (err) {
      console.error('Failed to load characters:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setNotice('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/characters/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          user_id: userId, 
          name, 
          age,
          race,
          concept,
          strength,
          dexterity,
          constitution,
          intelligence,
          wisdom,
          charisma,
          skills,
          weaknesses: [],
          statuses: statuses.map((status) => ({
            name: status.name,
            type: status.type,
            modifier: status.modifier,
            category: status.modifier >= 0 ? 'physical' : 'mental',
          })),
          inventory: inventory.map((item) => ({
            name: item.name,
            type: item.type,
            quantity: item.type === 'consumable' ? Math.max(1, item.quantity ?? 1) : 1,
            equipped: item.type === 'equipment' ? Boolean(item.equipped) : false,
            modifier: Number(item.modifier ?? 0),
            description: item.description?.trim() || undefined,
          })),
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create character');
      }

      await loadCharacters();
      resetForm();
      setShowCreateForm(false);
      setNotice('캐릭터가 생성되었습니다.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create character');
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCharacter) return;
    setError('');
    setNotice('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/characters/${editingCharacter.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          name, 
          age,
          race,
          concept,
          strength,
          dexterity,
          constitution,
          intelligence,
          wisdom,
          charisma,
          skills,
          weaknesses: [],
          statuses: statuses.map((status) => ({
            name: status.name,
            type: status.type,
            modifier: status.modifier,
            category: status.modifier >= 0 ? 'physical' : 'mental',
          })),
          inventory: inventory.map((item) => ({
            name: item.name,
            type: item.type,
            quantity: item.type === 'consumable' ? Math.max(1, item.quantity ?? 1) : 1,
            equipped: item.type === 'equipment' ? Boolean(item.equipped) : false,
            modifier: Number(item.modifier ?? 0),
            description: item.description?.trim() || undefined,
          })),
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to update character');
      }

      await loadCharacters();
      resetForm();
      setEditingCharacter(null);
      setNotice('캐릭터가 수정되었습니다.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update character');
    }
  };

  const handleDelete = async (characterId: number) => {
    if (!confirm('Are you sure you want to delete this character?')) return;
    setError('');
    setNotice('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/characters/${characterId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        await loadCharacters();
        setNotice('캐릭터가 삭제되었습니다.');
      }
    } catch (err) {
      console.error('Failed to delete character:', err);
      setError('Failed to delete character');
    }
  };

  const handleDuplicate = async (characterId: number) => {
    setError('');
    setNotice('');
    setDuplicatingCharacterId(characterId);

    try {
      const response = await fetch(`${API_BASE_URL}/api/characters/${characterId}/duplicate`, {
        method: 'POST',
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to duplicate character');
      }

      await loadCharacters();
      setNotice('캐릭터가 복제되었습니다.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to duplicate character');
    } finally {
      setDuplicatingCharacterId(null);
    }
  };

  const handleCreateShareCode = async (characterId: number) => {
    if (!userId) return;
    setError('');
    setNotice('');
    setSharingCharacterId(characterId);

    try {
      const response = await fetch(`${API_BASE_URL}/api/characters/${characterId}/share-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create share code');
      }

      const data = await response.json();
      setLatestShareCode({
        characterName: data.character_name,
        code: data.share_code,
      });
      setNotice('공유 코드가 생성되었습니다. 3분 내에 입력해야 합니다.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create share code');
    } finally {
      setSharingCharacterId(null);
    }
  };

  const handleConsumeInventoryItem = async (characterId: number, itemName: string) => {
    const key = `${characterId}:${itemName}`;
    setConsumingItemKey(key);
    setError('');
    setNotice('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/characters/${characterId}/inventory/consume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_name: itemName }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to consume item');
      }

      await loadCharacters();
      setNotice(`소모품 "${itemName}"을(를) 사용했습니다.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to consume item');
    } finally {
      setConsumingItemKey(null);
    }
  };

  const handleRedeemShareCode = async () => {
    if (!userId) return;

    const normalizedCode = shareCodeInput.trim();
    if (!/^\d{9}$/.test(normalizedCode)) {
      setError('공유 코드는 9자리 숫자여야 합니다.');
      return;
    }

    setError('');
    setNotice('');
    setRedeemingShareCode(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/characters/share/redeem`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, share_code: normalizedCode }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to redeem share code');
      }

      const data = await response.json();
      await loadCharacters();
      setShareCodeInput('');
      setNotice(`"${data.character.name}" 캐릭터를 공유받았습니다.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to redeem share code');
    } finally {
      setRedeemingShareCode(false);
    }
  };

  const resetForm = () => {
    setName('');
    setAge(25);
    setRace('인간');
    setConcept('');
    setStrength(10);
    setDexterity(10);
    setConstitution(10);
    setIntelligence(10);
    setWisdom(10);
    setCharisma(10);
    setSkills([]);
    setStatuses([]);
    setInventory([]);
    setNewSkillType('passive');
    setNewSkillName('');
    setNewSkillDescription('');
    setNewSkillAbility('');
    setNewStatusName('');
    setNewStatusType('debuff');
    setNewStatusModifier(-1);
    setNewItemName('');
    setNewItemType('equipment');
    setNewItemQuantity(1);
    setNewItemEquipped(false);
    setNewItemModifier(0);
    setNewItemDescription('');
    setError('');
    setNotice('');
  };

  const startEdit = (character: Character) => {
    setEditingCharacter(character);
    setName(character.name);
    setAge(character.data.age || 25);
    setRace(character.data.race || '인간');
    setConcept(character.data.concept || '');
    setStrength(character.data.strength || 10);
    setDexterity(character.data.dexterity || 10);
    setConstitution(character.data.constitution || 10);
    setIntelligence(character.data.intelligence || 10);
    setWisdom(character.data.wisdom || 10);
    setCharisma(character.data.charisma || 10);
    setSkills(character.data.skills || []);
    const sourceStatuses: EditableStatus[] = character.data.statuses && character.data.statuses.length > 0
      ? character.data.statuses
          : (character.data.weaknesses || []).map((weakness) =>
          typeof weakness === 'string'
            ? { name: weakness, type: 'debuff', modifier: -1 }
            : { name: weakness.name, type: 'debuff', modifier: -1 },
        );
    setStatuses(
      sourceStatuses
        .map((status): EditableStatus => ({
          name: status.name,
          type: status.type === 'buff' ? 'buff' : 'debuff',
          modifier: Number(status.modifier ?? 0),
        }))
        .filter((status) => status.name.trim()),
    );
    setInventory(
      (character.data.inventory || []).map((item) => {
        if (typeof item === 'string') {
          return {
            name: item,
            type: 'equipment',
            quantity: 1,
            equipped: false,
            modifier: 0,
            description: '',
          } as EditableInventoryItem;
        }
        return {
          name: item.name,
          type: item.type === 'consumable' ? 'consumable' : 'equipment',
          quantity: Math.max(1, Number(item.quantity ?? 1)),
          equipped: Boolean(item.equipped),
          modifier: Number(item.modifier ?? 0),
          description: item.description || '',
        } as EditableInventoryItem;
      }),
    );
    setShowCreateForm(false);
  };

  const cancelForm = () => {
    setShowCreateForm(false);
    setEditingCharacter(null);
    resetForm();
  };

  const addSkill = () => {
    if (newSkillName.trim() && newSkillDescription.trim()) {
      setSkills([...skills, {
        type: newSkillType,
        name: newSkillName.trim(),
        description: newSkillDescription.trim(),
        ...(newSkillAbility ? { ability: newSkillAbility } : {}),
      }]);
      setNewSkillType('passive');
      setNewSkillName('');
      setNewSkillDescription('');
      setNewSkillAbility('');
    }
  };

  const removeSkill = (index: number) => {
    setSkills(skills.filter((_, i) => i !== index));
  };

  const addStatus = () => {
    const name = newStatusName.trim();
    if (!name || statuses.some((status) => status.name === name)) {
      return;
    }
    setStatuses([
      ...statuses,
      {
        name,
        type: newStatusType,
        modifier: Number(newStatusModifier || 0),
      },
    ]);
    setNewStatusName('');
    setNewStatusModifier(newStatusType === 'buff' ? 1 : -1);
  };

  const removeStatus = (name: string) => {
    setStatuses(statuses.filter((status) => status.name !== name));
  };

  const addInventoryItem = () => {
    const name = newItemName.trim();
    if (!name) {
      return;
    }

    setInventory([
      ...inventory,
      {
        name,
        type: newItemType,
        quantity: newItemType === 'consumable' ? Math.max(1, Number(newItemQuantity || 1)) : 1,
        equipped: newItemType === 'equipment' ? newItemEquipped : false,
        modifier: Number(newItemModifier || 0),
        description: newItemDescription.trim(),
      },
    ]);

    setNewItemName('');
    setNewItemType('equipment');
    setNewItemQuantity(1);
    setNewItemEquipped(false);
    setNewItemModifier(0);
    setNewItemDescription('');
  };

  const removeInventoryItem = (index: number) => {
    setInventory(inventory.filter((_, itemIndex) => itemIndex !== index));
  };

  const calculateModifier = (score: number): number => {
    return Math.floor((score - 10) / 2);
  };

  const actionButtonBase =
    'inline-flex w-full items-center justify-center rounded-md border px-2.5 py-2 text-[11px] sm:text-xs font-semibold tracking-wide transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-45 disabled:cursor-not-allowed';
  const actionButtonStyle = {
    select: `${actionButtonBase} border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 focus-visible:ring-emerald-300`,
    selected: `${actionButtonBase} border-emerald-400 bg-emerald-200 text-emerald-900 shadow-sm`,
    edit: `${actionButtonBase} border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus-visible:ring-slate-300`,
    duplicate: `${actionButtonBase} border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus-visible:ring-slate-300`,
    share: `${actionButtonBase} border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus-visible:ring-slate-300`,
    delete: `${actionButtonBase} border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100 focus-visible:ring-rose-300`,
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-slate-700 text-xl">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-800 mb-2">캐릭터 관리</h1>
            <p className="text-slate-500">환영합니다, {username}님!</p>
          </div>
          <button
            onClick={logout}
            className="bg-slate-200 hover:bg-slate-300 text-slate-700 px-4 py-2 rounded-lg transition-colors border border-slate-300 font-medium"
          >
            로그아웃
          </button>
        </div>

        {/* Create/Edit Form */}
        {(showCreateForm || editingCharacter) && (
          <div className="bg-white p-6 rounded-xl shadow-card mb-6 border border-slate-200">
            <h2 className="text-xl font-bold text-slate-800 mb-4">
              {editingCharacter ? '캐릭터 수정' : '새 캐릭터 생성'}
            </h2>
            <form onSubmit={editingCharacter ? handleUpdate : handleCreate} className="space-y-6">
              {/* 기본 정보 */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-700 border-b pb-2">기본 정보</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">이름 *</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">나이</label>
                    <input
                      type="number"
                      value={age}
                      onChange={(e) => setAge(Number(e.target.value))}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      min="1"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">종족</label>
                  <input
                    type="text"
                    value={race}
                    onChange={(e) => setRace(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                    placeholder="예: 인간, 엘프, 드워프..."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">컨셉/배경</label>
                  <textarea
                    value={concept}
                    onChange={(e) => setConcept(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                    rows={2}
                    placeholder="캐릭터의 배경이나 컨셉을 간단히 설명해주세요"
                  />
                </div>
              </div>

              {/* D20 능력치 */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-700 border-b pb-2">능력치 (D20 시스템)</h3>
                <p className="text-xs text-slate-500">10 = 평균, 14-15 = 전문가, 18+ = 천재</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      근력 (STR) <span className="text-xs text-slate-500">({calculateModifier(strength) >= 0 ? '+' : ''}{calculateModifier(strength)})</span>
                    </label>
                    <input
                      type="number"
                      value={strength}
                      onChange={(e) => setStrength(Number(e.target.value))}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      min="1"
                      max="30"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      민첩 (DEX) <span className="text-xs text-slate-500">({calculateModifier(dexterity) >= 0 ? '+' : ''}{calculateModifier(dexterity)})</span>
                    </label>
                    <input
                      type="number"
                      value={dexterity}
                      onChange={(e) => setDexterity(Number(e.target.value))}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      min="1"
                      max="30"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      건강 (CON) <span className="text-xs text-slate-500">({calculateModifier(constitution) >= 0 ? '+' : ''}{calculateModifier(constitution)})</span>
                    </label>
                    <input
                      type="number"
                      value={constitution}
                      onChange={(e) => setConstitution(Number(e.target.value))}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      min="1"
                      max="30"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      지능 (INT) <span className="text-xs text-slate-500">({calculateModifier(intelligence) >= 0 ? '+' : ''}{calculateModifier(intelligence)})</span>
                    </label>
                    <input
                      type="number"
                      value={intelligence}
                      onChange={(e) => setIntelligence(Number(e.target.value))}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      min="1"
                      max="30"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      지혜 (WIS) <span className="text-xs text-slate-500">({calculateModifier(wisdom) >= 0 ? '+' : ''}{calculateModifier(wisdom)})</span>
                    </label>
                    <input
                      type="number"
                      value={wisdom}
                      onChange={(e) => setWisdom(Number(e.target.value))}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      min="1"
                      max="30"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      매력 (CHA) <span className="text-xs text-slate-500">({calculateModifier(charisma) >= 0 ? '+' : ''}{calculateModifier(charisma)})</span>
                    </label>
                    <input
                      type="number"
                      value={charisma}
                      onChange={(e) => setCharisma(Number(e.target.value))}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      min="1"
                      max="30"
                    />
                  </div>
                </div>
              </div>

              {/* 스킬 */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-700 border-b pb-2">스킬</h3>
                <div className="space-y-3 bg-slate-50 p-4 rounded-lg">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">타입</label>
                      <select
                        value={newSkillType}
                        onChange={(e) => setNewSkillType(e.target.value as 'passive' | 'active')}
                        className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                      >
                        <option value="passive">Passive (패시브)</option>
                        <option value="active">Active (액티브)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">주요 능력치</label>
                      <select
                        value={newSkillAbility}
                        onChange={(e) => setNewSkillAbility(e.target.value as AbilityKey | '')}
                        className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                      >
                        <option value="">선택 안함</option>
                        {(Object.keys(ABILITY_LABELS) as AbilityKey[]).map((key) => (
                          <option key={key} value={key}>
                            {ABILITY_SHORT_LABELS[key]} ({ABILITY_LABELS[key]})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">스킬 이름</label>
                      <input
                        type="text"
                        value={newSkillName}
                        onChange={(e) => setNewSkillName(e.target.value)}
                        placeholder="예: 정밀 사격"
                        className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">스킬 설명</label>
                    <textarea
                      value={newSkillDescription}
                      onChange={(e) => setNewSkillDescription(e.target.value)}
                      placeholder="스킬의 효과나 특징을 설명해주세요. AI가 이를 참고하여 판정합니다."
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                      rows={2}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={addSkill}
                    className="w-full bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium"
                  >
                    + 스킬 추가
                  </button>
                </div>
                {skills.length > 0 && (
                  <div className="space-y-2">
                    {skills.map((skill, index) => (
                      <div key={index} className="bg-white border border-slate-200 p-3 rounded-lg">
                        <div className="flex justify-between items-start mb-1">
                          <div className="flex items-center gap-2">
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              skill.type === 'passive'
                                ? 'bg-purple-100 text-purple-700'
                                : 'bg-orange-100 text-orange-700'
                            }`}>
                              {skill.type === 'passive' ? 'Passive' : 'Active'}
                            </span>
                            {skill.ability && (
                              <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700">
                                {ABILITY_SHORT_LABELS[skill.ability as AbilityKey] || skill.ability}
                              </span>
                            )}
                            <span className="font-semibold text-slate-800">{skill.name}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeSkill(index)}
                            className="text-red-600 hover:text-red-800 font-bold text-lg leading-none"
                          >
                            ×
                          </button>
                        </div>
                        <p className="text-sm text-slate-600">{skill.description}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-700 border-b pb-2">상태</h3>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                  <input
                    type="text"
                    value={newStatusName}
                    onChange={(e) => setNewStatusName(e.target.value)}
                    placeholder="상태 이름"
                    className="sm:col-span-2 px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                  />
                  <select
                    value={newStatusType}
                    onChange={(e) => setNewStatusType(e.target.value as 'buff' | 'debuff')}
                    className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                  >
                    <option value="buff">버프</option>
                    <option value="debuff">디버프</option>
                  </select>
                  <input
                    type="number"
                    value={newStatusModifier}
                    onChange={(e) => setNewStatusModifier(Number(e.target.value))}
                    className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                  />
                </div>
                <div>
                  <button
                    type="button"
                    onClick={addStatus}
                    className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors"
                  >
                    상태 추가
                  </button>
                </div>
                {statuses.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {statuses.map((status) => (
                      <div
                        key={status.name}
                        className={`${status.type === 'buff' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'} px-3 py-1 rounded-full text-sm flex items-center gap-2`}
                      >
                        <span>{status.name} ({status.modifier >= 0 ? '+' : ''}{status.modifier})</span>
                        <button
                          type="button"
                          onClick={() => removeStatus(status.name)}
                          className="font-bold"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-700 border-b pb-2">인벤토리</h3>
                <div className="space-y-2 bg-slate-50 p-4 rounded-lg">
                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                    <input
                      type="text"
                      value={newItemName}
                      onChange={(e) => setNewItemName(e.target.value)}
                      placeholder="아이템 이름"
                      className="sm:col-span-2 px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                    />
                    <select
                      value={newItemType}
                      onChange={(e) => setNewItemType(e.target.value as InventoryItemType)}
                      className="px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                    >
                      <option value="equipment">장비</option>
                      <option value="consumable">소모품</option>
                    </select>
                    <input
                      type="number"
                      min="1"
                      value={newItemQuantity}
                      onChange={(e) => setNewItemQuantity(Number(e.target.value))}
                      disabled={newItemType === 'equipment'}
                      className="px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm disabled:bg-slate-100"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={newItemEquipped}
                        onChange={(e) => setNewItemEquipped(e.target.checked)}
                        disabled={newItemType === 'consumable'}
                        className="rounded border-slate-300"
                      />
                      장착
                    </label>
                    <input
                      type="number"
                      value={newItemModifier}
                      onChange={(e) => setNewItemModifier(Number(e.target.value))}
                      placeholder="보정치"
                      className="px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                    />
                    <input
                      type="text"
                      value={newItemDescription}
                      onChange={(e) => setNewItemDescription(e.target.value)}
                      placeholder="설명"
                      className="px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={addInventoryItem}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium"
                  >
                    인벤토리 추가
                  </button>
                </div>
                {inventory.length > 0 && (
                  <div className="space-y-2">
                    {inventory.map((item, index) => {
                      const itemModifier = Number(item.modifier ?? 0);
                      return (
                      <div key={`${item.name}-${index}`} className="bg-white border border-slate-200 p-3 rounded-lg text-sm flex justify-between gap-2">
                        <div>
                          <div className="font-semibold text-slate-800">{item.name}</div>
                          <div className="text-xs text-slate-600">
                            {item.type === 'consumable' ? `소모품 x${item.quantity}` : `장비${item.equipped ? ' (장착)' : ''}`}
                            {itemModifier !== 0 ? ` · 보정 ${itemModifier >= 0 ? '+' : ''}${itemModifier}` : ''}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeInventoryItem(index)}
                          className="text-red-600 hover:text-red-800 font-bold"
                        >
                          ×
                        </button>
                      </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}
              
              <div className="flex gap-3 pt-4">
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors shadow-sm"
                >
                  {editingCharacter ? '수정' : '생성'}
                </button>
                <button
                  type="button"
                  onClick={cancelForm}
                  className="flex-1 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold py-3 px-4 rounded-lg transition-colors border border-slate-300"
                >
                  취소
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Create Button */}
        {!showCreateForm && !editingCharacter && (
          <button
            onClick={() => setShowCreateForm(true)}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors mb-6 shadow-sm"
          >
            + 새 캐릭터 생성
          </button>
        )}

        {!showCreateForm && !editingCharacter && (
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-card mb-6">
            <h3 className="text-base font-semibold text-slate-800 mb-3">공유 코드로 캐릭터 받기</h3>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={9}
                value={shareCodeInput}
                onChange={(e) => setShareCodeInput(e.target.value.replace(/[^0-9]/g, ''))}
                placeholder="9자리 공유 코드 입력"
                className="flex-1 px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              />
              <button
                type="button"
                onClick={handleRedeemShareCode}
                disabled={redeemingShareCode}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg transition-colors font-medium"
              >
                {redeemingShareCode ? '받는 중...' : '코드로 받기'}
              </button>
            </div>
            {latestShareCode && (
              <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-800">
                  <span className="font-semibold">{latestShareCode.characterName}</span> 공유 코드:
                  <span className="ml-2 font-mono font-bold text-base tracking-wider">{latestShareCode.code}</span>
                  <span className="ml-2 text-xs text-amber-700">(3분 유효)</span>
                </p>
              </div>
            )}
          </div>
        )}

        {/* Character List */}
        {notice && !showCreateForm && !editingCharacter && (
          <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
            {notice}
          </div>
        )}
        {error && !showCreateForm && !editingCharacter && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}
        <div className="space-y-4">
          {characters.length === 0 ? (
            <div className="bg-white p-8 rounded-xl text-center border border-slate-200 shadow-card">
              <p className="text-slate-500">아직 캐릭터가 없습니다. 새로 만들어보세요!</p>
            </div>
          ) : (
            characters.map((character) => {
              const isSelectedCharacter = currentCharacter?.id === character.id;

              return (
                <div
                  key={character.id}
                  className="bg-white p-6 rounded-xl shadow-card border border-slate-200 hover:shadow-card-hover transition-all"
                >
                <div className="mb-4 rounded-lg border border-slate-200 bg-slate-100 p-1.5">
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
                    <button
                      onClick={() => onSelectCharacter(character)}
                      className={isSelectedCharacter ? actionButtonStyle.selected : actionButtonStyle.select}
                      aria-pressed={isSelectedCharacter}
                    >
                      {isSelectedCharacter ? '선택됨' : '선택'}
                    </button>
                    <button
                      onClick={() => startEdit(character)}
                      className={actionButtonStyle.edit}
                    >
                      수정
                    </button>
                    <button
                      onClick={() => handleDuplicate(character.id)}
                      disabled={duplicatingCharacterId === character.id}
                      className={actionButtonStyle.duplicate}
                    >
                      {duplicatingCharacterId === character.id ? '복제 중...' : '복제'}
                    </button>
                    <button
                      onClick={() => handleCreateShareCode(character.id)}
                      disabled={sharingCharacterId === character.id}
                      className={actionButtonStyle.share}
                    >
                      {sharingCharacterId === character.id ? '코드 생성 중...' : '공유코드'}
                    </button>
                    <button
                      onClick={() => handleDelete(character.id)}
                      className={actionButtonStyle.delete}
                    >
                      삭제
                    </button>
                  </div>
                </div>

                <div className="mb-4">
                    <h3 className="text-xl font-bold text-slate-800 mb-1">{character.name}</h3>
                    <p className="text-sm text-slate-500">
                      {character.data.race || '인간'} • {character.data.age || 25}세
                    </p>
                    {character.data.concept && (
                      <p className="text-sm text-slate-600 mt-1 italic">{character.data.concept}</p>
                    )}
                </div>
                
                {/* 능력치 */}
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-sm text-slate-700 bg-slate-50 p-3 rounded-lg">
                  <div className="text-center">
                    <div className="text-xs text-slate-500">STR</div>
                    <div className="font-bold">{character.data.strength || 10}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-500">DEX</div>
                    <div className="font-bold">{character.data.dexterity || 10}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-500">CON</div>
                    <div className="font-bold">{character.data.constitution || 10}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-500">INT</div>
                    <div className="font-bold">{character.data.intelligence || 10}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-500">WIS</div>
                    <div className="font-bold">{character.data.wisdom || 10}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-500">CHA</div>
                    <div className="font-bold">{character.data.charisma || 10}</div>
                  </div>
                </div>
                
                {/* 스킬 */}
                {character.data.skills && character.data.skills.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs text-slate-500 mb-2">스킬:</p>
                    <div className="space-y-1">
                      {character.data.skills.map((skill, index) => (
                        <div key={index} className="bg-slate-50 p-2 rounded text-xs">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`px-1.5 py-0.5 rounded text-xs ${
                              skill.type === 'passive'
                                ? 'bg-purple-100 text-purple-700'
                                : 'bg-orange-100 text-orange-700'
                            }`}>
                              {skill.type === 'passive' ? 'P' : 'A'}
                            </span>
                            {skill.ability && (
                              <span className="px-1.5 py-0.5 rounded text-xs bg-blue-100 text-blue-700">
                                {ABILITY_SHORT_LABELS[skill.ability as AbilityKey] || skill.ability}
                              </span>
                            )}
                            <span className="font-semibold text-slate-800">{skill.name}</span>
                          </div>
                          <p className="text-slate-600 text-xs">{skill.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {((character.data.statuses && character.data.statuses.length > 0) || (character.data.weaknesses && character.data.weaknesses.length > 0)) && (
                  <div className="mt-2">
                    <p className="text-xs text-slate-500 mb-1">상태:</p>
                    <div className="flex flex-wrap gap-1">
                      {(character.data.statuses && character.data.statuses.length > 0
                        ? character.data.statuses.map((status) => ({
                            name: status.name,
                            type: status.type === 'buff' ? 'buff' : 'debuff',
                            modifier: Number(status.modifier ?? 0),
                          }))
                        : (character.data.weaknesses || []).map((weakness) => ({
                            name: typeof weakness === 'string' ? weakness : weakness.name,
                            type: 'debuff' as const,
                            modifier: -1,
                          }))
                      ).map((status, idx) => {
                        const statusName = status.name;
                        const statusType = status.type;
                        const modifier = status.modifier;
                        return (
                          <span
                            key={`${statusName}-${idx}`}
                            className={`${statusType === 'buff' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'} px-2 py-0.5 rounded text-xs`}
                          >
                            {statusName} ({modifier >= 0 ? '+' : ''}{modifier})
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}

                {character.data.inventory && character.data.inventory.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs text-slate-500 mb-1">인벤토리:</p>
                    <div className="space-y-1">
                      {character.data.inventory.map((item, idx) => {
                        if (typeof item === 'string') {
                          return (
                            <div key={`${item}-${idx}`} className="text-xs bg-slate-50 px-2 py-1 rounded text-slate-700">
                              {item}
                            </div>
                          );
                        }

                        const quantity = item.type === 'consumable' ? ` x${Math.max(1, Number(item.quantity ?? 1))}` : '';
                        const equipped = item.type === 'equipment' && item.equipped ? ' (장착)' : '';
                        const modifier = item.modifier ? ` · ${item.modifier >= 0 ? '+' : ''}${item.modifier}` : '';
                        const typeLabel = item.type === 'consumable' ? '소모품' : '장비';
                        const consumeKey = `${character.id}:${item.name}`;
                        return (
                          <div key={`${item.name}-${idx}`} className="text-xs bg-slate-50 px-2 py-1 rounded text-slate-700 flex items-center justify-between gap-2">
                            <span>{item.name} [{typeLabel}]{quantity}{equipped}{modifier}</span>
                            {item.type === 'consumable' && (
                              <button
                                type="button"
                                disabled={consumingItemKey === consumeKey}
                                onClick={() => handleConsumeInventoryItem(character.id, item.name)}
                                className="text-[10px] px-2 py-0.5 rounded bg-indigo-600 text-white disabled:bg-indigo-300"
                              >
                                {consumingItemKey === consumeKey ? '사용 중' : '사용'}
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
