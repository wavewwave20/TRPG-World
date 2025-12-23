import { useState, useEffect } from 'react';
import { useAuthStore } from '../stores/authStore';
import type { Character as BaseCharacter, Skill as BaseSkill } from '../types/character';

interface Skill extends BaseSkill {
  type: 'passive' | 'active';
  description: string;
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
    weaknesses: string[];
    status_effects: string[];
    inventory: any[];
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
  
  // Weaknesses
  const [weaknesses, setWeaknesses] = useState<string[]>([]);
  const [newWeakness, setNewWeakness] = useState('');
  
  const [error, setError] = useState('');
  
  const userId = useAuthStore((state) => state.userId);
  const username = useAuthStore((state) => state.username);
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    loadCharacters();
  }, [userId]);

  const loadCharacters = async () => {
    if (!userId) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/characters/user/${userId}`);
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

    try {
      const response = await fetch('http://localhost:8000/api/characters/', {
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
          weaknesses
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create character');
      }

      await loadCharacters();
      resetForm();
      setShowCreateForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create character');
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCharacter) return;
    setError('');

    try {
      const response = await fetch(`http://localhost:8000/api/characters/${editingCharacter.id}`, {
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
          weaknesses
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to update character');
      }

      await loadCharacters();
      resetForm();
      setEditingCharacter(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update character');
    }
  };

  const handleDelete = async (characterId: number) => {
    if (!confirm('Are you sure you want to delete this character?')) return;

    try {
      const response = await fetch(`http://localhost:8000/api/characters/${characterId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        await loadCharacters();
      }
    } catch (err) {
      console.error('Failed to delete character:', err);
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
    setWeaknesses([]);
    setNewSkillType('passive');
    setNewSkillName('');
    setNewSkillDescription('');
    setNewWeakness('');
    setError('');
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
    setWeaknesses(character.data.weaknesses || []);
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
        description: newSkillDescription.trim()
      }]);
      setNewSkillType('passive');
      setNewSkillName('');
      setNewSkillDescription('');
    }
  };

  const removeSkill = (index: number) => {
    setSkills(skills.filter((_, i) => i !== index));
  };

  const addWeakness = () => {
    if (newWeakness.trim() && !weaknesses.includes(newWeakness.trim())) {
      setWeaknesses([...weaknesses, newWeakness.trim()]);
      setNewWeakness('');
    }
  };

  const removeWeakness = (weakness: string) => {
    setWeaknesses(weaknesses.filter(w => w !== weakness));
  };

  const calculateModifier = (score: number): number => {
    return Math.floor((score - 10) / 2);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-slate-700 text-xl">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-8">
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
                <div className="grid grid-cols-2 gap-4">
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
                <div className="grid grid-cols-3 gap-4">
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
                  <div className="grid grid-cols-2 gap-3">
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

              {/* 약점 */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-700 border-b pb-2">약점</h3>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newWeakness}
                    onChange={(e) => setNewWeakness(e.target.value)}
                    placeholder="약점 입력"
                    className="flex-1 px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                  />
                  <button
                    type="button"
                    onClick={addWeakness}
                    className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors"
                  >
                    추가
                  </button>
                </div>
                {weaknesses.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {weaknesses.map((weakness) => (
                      <div key={weakness} className="bg-red-100 text-red-800 px-3 py-1 rounded-full text-sm flex items-center gap-2">
                        <span>{weakness}</span>
                        <button
                          type="button"
                          onClick={() => removeWeakness(weakness)}
                          className="text-red-600 hover:text-red-800 font-bold"
                        >
                          ×
                        </button>
                      </div>
                    ))}
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

        {/* Character List */}
        <div className="space-y-4">
          {characters.length === 0 ? (
            <div className="bg-white p-8 rounded-xl text-center border border-slate-200 shadow-card">
              <p className="text-slate-500">아직 캐릭터가 없습니다. 새로 만들어보세요!</p>
            </div>
          ) : (
            characters.map((character) => (
              <div
                key={character.id}
                className="bg-white p-6 rounded-xl shadow-card border border-slate-200 hover:shadow-card-hover transition-all"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="flex-1">
                    <h3 className="text-xl font-bold text-slate-800 mb-1">{character.name}</h3>
                    <p className="text-sm text-slate-500">
                      {character.data.race || '인간'} • {character.data.age || 25}세
                    </p>
                    {character.data.concept && (
                      <p className="text-sm text-slate-600 mt-1 italic">{character.data.concept}</p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => onSelectCharacter(character)}
                      className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium shadow-sm"
                    >
                      선택
                    </button>
                    <button
                      onClick={() => startEdit(character)}
                      className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium shadow-sm"
                    >
                      수정
                    </button>
                    <button
                      onClick={() => handleDelete(character.id)}
                      className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium shadow-sm"
                    >
                      삭제
                    </button>
                  </div>
                </div>
                
                {/* 능력치 */}
                <div className="grid grid-cols-6 gap-2 text-sm text-slate-700 bg-slate-50 p-3 rounded-lg">
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
                            <span className="font-semibold text-slate-800">{skill.name}</span>
                          </div>
                          <p className="text-slate-600 text-xs">{skill.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* 약점 */}
                {character.data.weaknesses && character.data.weaknesses.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs text-slate-500 mb-1">약점:</p>
                    <div className="flex flex-wrap gap-1">
                      {character.data.weaknesses.map((weakness) => (
                        <span key={weakness} className="bg-red-100 text-red-800 px-2 py-0.5 rounded text-xs">
                          {weakness}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
