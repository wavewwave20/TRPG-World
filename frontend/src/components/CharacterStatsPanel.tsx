import { useState } from 'react';
import type { Character } from '../types/character';

interface CharacterStatsPanelProps {
  character: Character;
}

export default function CharacterStatsPanel({ character }: CharacterStatsPanelProps) {
  const [skillsExpanded, setSkillsExpanded] = useState(true);

  const { data } = character;

  // Ability scores in display order
  const abilityScores = [
    { name: 'STR', label: '근력', value: data.strength },
    { name: 'DEX', label: '민첩', value: data.dexterity },
    { name: 'CON', label: '건강', value: data.constitution },
    { name: 'INT', label: '지능', value: data.intelligence },
    { name: 'WIS', label: '지혜', value: data.wisdom },
    { name: 'CHA', label: '매력', value: data.charisma },
  ];

  return (
    <div 
      className="bg-white rounded-lg border border-slate-200 shadow-sm"
      role="region"
      aria-label={`${character.name} 캐릭터 정보`}
    >
      {/* Character Name Header */}
      <div className="bg-slate-50 px-4 py-3 border-b border-slate-200 sticky top-0">
        <h3 className="text-lg font-bold text-slate-800" id="character-name-heading">{character.name}</h3>
        {(data.race || data.age) && (
          <p className="text-xs text-slate-500 mt-0.5" aria-label={`${data.race ? data.race : ''}${data.race && data.age ? ', ' : ''}${data.age ? data.age + '세' : ''}`}>
            {data.race && <span>{data.race}</span>}
            {data.race && data.age && <span aria-hidden="true"> • </span>}
            {data.age && <span>{data.age}세</span>}
          </p>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Concept/Background */}
        {data.concept && (
          <div 
            className="text-sm text-slate-600 italic border-l-2 border-slate-300 pl-3"
            role="note"
            aria-label="캐릭터 컨셉"
          >
            {data.concept}
          </div>
        )}

        {/* Ability Scores Grid (3x2) */}
        <div role="group" aria-labelledby="ability-scores-heading">
          <h4 id="ability-scores-heading" className="text-xs font-semibold text-slate-500 uppercase mb-2">능력치</h4>
          <div className="grid grid-cols-3 gap-2">
            {abilityScores.map((ability) => {
              return (
                <div
                  key={ability.name}
                  className="bg-slate-50 rounded-lg p-2 text-center border border-slate-200"
                  role="group"
                  aria-label={`${ability.label} ${ability.value}`}
                >
                  <div className="text-xs text-slate-500 mb-1" aria-hidden="true">{ability.name}</div>
                  <div className="text-lg font-bold text-slate-800" aria-hidden="true">{ability.value}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Skills (Collapsible) */}
        {data.skills && data.skills.length > 0 && (
          <div role="region" aria-labelledby="skills-heading">
            <button
              onClick={() => setSkillsExpanded(!skillsExpanded)}
              className="w-full flex items-center justify-between text-xs font-semibold text-slate-500 uppercase mb-2 hover:text-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded px-1"
              aria-expanded={skillsExpanded}
              aria-controls="skills-list"
              aria-label={`스킬 목록 ${skillsExpanded ? '접기' : '펼치기'}, 총 ${data.skills.length}개`}
            >
              <span id="skills-heading" aria-hidden="true">스킬 ({data.skills.length})</span>
              <span className="text-lg" aria-hidden="true">{skillsExpanded ? '−' : '+'}</span>
            </button>
            {skillsExpanded && (
              <div id="skills-list" className="space-y-2" role="list">
                {data.skills.map((skill, index) => (
                  <div
                    key={index}
                    className="bg-slate-50 rounded-lg p-2 border border-slate-200"
                    role="listitem"
                    aria-label={`${skill.name}${skill.type ? `, ${skill.type === 'passive' ? '패시브' : '액티브'}` : ''}${skill.description ? `: ${skill.description}` : ''}`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {skill.type && (
                        <span
                          className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            skill.type === 'passive'
                              ? 'bg-purple-100 text-purple-700'
                              : 'bg-orange-100 text-orange-700'
                          }`}
                          aria-label={skill.type === 'passive' ? '패시브' : '액티브'}
                        >
                          {skill.type === 'passive' ? 'P' : 'A'}
                        </span>
                      )}
                      <span className="text-sm font-semibold text-slate-800">
                        {skill.name}
                      </span>
                    </div>
                    {skill.description && (
                      <p className="text-xs text-slate-600">{skill.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Weaknesses */}
        {data.weaknesses && data.weaknesses.length > 0 && (
          <div role="group" aria-labelledby="weaknesses-heading">
            <h4 id="weaknesses-heading" className="text-xs font-semibold text-slate-500 uppercase mb-2">약점</h4>
            <div className="flex flex-wrap gap-1.5" role="list" aria-label={`약점 목록, 총 ${data.weaknesses.length}개`}>
              {data.weaknesses.map((weakness, index) => (
                <span
                  key={index}
                  className="bg-red-100 text-red-800 px-2 py-1 rounded text-xs font-medium"
                  role="listitem"
                >
                  {weakness}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Status Effects */}
        {data.status_effects && data.status_effects.length > 0 && (
          <div role="group" aria-labelledby="status-effects-heading">
            <h4 id="status-effects-heading" className="text-xs font-semibold text-slate-500 uppercase mb-2">상태 효과</h4>
            <div className="flex flex-wrap gap-1.5" role="list" aria-label={`상태 효과 목록, 총 ${data.status_effects.length}개`}>
              {data.status_effects.map((effect, index) => (
                <span
                  key={index}
                  className="bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs font-medium"
                  role="listitem"
                >
                  {effect}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
