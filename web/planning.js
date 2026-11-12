// Pure state transitions: no network, graph edits or video execution.
const copy = value => JSON.parse(JSON.stringify(value));
export function applyStoryboard(state, packet) {
  if(packet?.schema!=='shot-storyboard/1'||!packet.revision||!packet.workspace?.shots?.length)throw Error('No reviewed storyboard to apply.');
  if(state.shots.some(s=>['queued','running'].includes(s.job?.status)))throw Error('Finish generation before replacing the shot list.');
  const source=copy(packet.workspace),assets=copy(state.assets);
  for(const asset of source.assets){
    const existing=assets.find(a=>a.id===asset.id);
    if(existing&&JSON.stringify(existing)!==JSON.stringify(asset))throw Error(`Asset ID conflict: ${asset.name||asset.id}. Rename the asset before applying.`);
    if(!existing)assets.push(asset);
  }
  const next={...copy(state),...source,assets,storyboard_source_revision:packet.revision};
  // Absence of a director in the source must also clear a previously imported profile.
  if(!source.director_skill)delete next.director_skill;
  if(source.director_skill_enabled===undefined)next.director_skill_enabled=!!source.director_skill;
  for(const key of ['story_draft','script_plan_draft'])delete next[key];
  return next;
}
export const profileLabel = path => ({anderson:'Wes Anderson',wilder:'Billy Wilder',coen:'Coen brothers',fincher:'David Fincher',ozu:'Yasujiro Ozu',baseline:'Natural baseline'}[path.split('/').at(-1).replace(/\.md$/,'')] || path.split('/').at(-1).replace(/\.md$/,'').replaceAll('-',' '));
export const activeDirectorSkill = state => state.director_skill_enabled === false ? null : state.director_skill || null;
export const planBasis = state => JSON.stringify([state.script || '', activeDirectorSkill(state), state.llm_config || null]);
export const storyPlanBasis = state => JSON.stringify([state.rough_idea || '', state.story_target_duration_s ?? 40, activeDirectorSkill(state), state.llm_config || null,(state.assets||[]).map(a=>[a.id,a.name,a.image,a.description])]);
export const developmentBasis = state => JSON.stringify([state.rough_idea || '', state.story_target_duration_s ?? 40, planBasis(state)]);
export function timingSummary(timing) {
  if (!timing) return 'Not run yet';
  const ms=timing.total_ms ?? timing.llm_ms, calls=timing.calls || [];
  const speeds=calls.map(call=>call.provider_timings?.predicted_per_second).filter(Number.isFinite);
  return `${timing.status==='failed'?'Failed · ':''}${Number.isFinite(ms)?`${(ms/1000).toFixed(2)} s wall`:'Wall time unavailable'} · ${timing.model||calls[0]?.model||'Model unavailable'}${calls[0]?.base_url?` · Provider ${calls[0].base_url}`:''} · ${Math.max(0,calls.length-1)} retries · ${speeds.length?`Provider decode ${speeds.map(v=>v.toFixed(2)).join(', ')} tok/s`:'Provider decode TPS unavailable'}`;
}
export function storeDevelopment(state, result, basis) {
  if (developmentBasis(state) !== basis) throw Error('Idea, scene target, script, director or model settings changed. Develop the idea again.');
  if (typeof result.script !== 'string' || !result.script.trim()) throw Error('No complete story draft returned.');
  state.story_draft = {...copy(result), basis};
}
export function acceptDevelopment(state) {
  const draft = state.story_draft;
  if (!draft || developmentBasis(state) !== draft.basis) throw Error('Idea, scene target, script, director or model settings changed. Review a fresh draft.');
  state.script = draft.script;
  state.story_title = draft.title || '';
  state.story_development_timing = draft.timing;
  delete state.story_draft;
  delete state.script_plan_draft;
}
export function selectionBasis(state, id) {
  const shot = state.shots.find(s => s.id === id);
  return JSON.stringify([shot && [shot.title, shot.brief, shot.dialogue, shot.refs],
    state.assets.map(a => [a.id, a.name, a.image, a.description]), state.llm_config || null]);
}
export function appendPlan(state, draft, uid) {
  if ((draft.input_mode==='story'?storyPlanBasis(state):planBasis(state)) !== draft.basis) throw Error('Story, script, skill or model settings changed. Plan again before adding shots.');
  if (!Array.isArray(draft.shots) || !draft.shots.length) throw Error('No complete shot plan to add.');
  const ids = Object.fromEntries(draft.shots.map(s => [s.shot_key, uid()]));
  const added = draft.shots.map(s => ({id: ids[s.shot_key], title: s.title, brief: s.brief,
    duration_s: s.duration_s, width: draft.width || 704, height: draft.height || 480, refs: [],
    ...(s.dialogue ? {dialogue: s.dialogue} : {}),
    continuity: {mode: s.continuity.mode, ...(s.continuity.mode === 'continue' ? {source_shot_id: ids[s.continuity.source_shot_key]} : {})},
    plan_source: {excerpt: s.source_excerpt, shot_key: s.shot_key, rule_manifest: draft.rule_manifest,
      ...(draft.source_kind?{source_kind:draft.source_kind}:{}),
      ...(s.dramatic_beat && draft.story_events ? {brief_basis:s.brief,dialogue_basis:s.dialogue||'',dramatic_beat:copy(s.dramatic_beat),
        story_events:copy(draft.story_events.filter(e=>s.dramatic_beat.event_keys.includes(e.event_key)))} : {})}}));
  if(draft.input_mode==='story')state.shots=added;
  else state.shots.push(...added);
  state.active_shot_id = added[0].id;
  if(draft.input_mode==='story')state.story_title=draft.title||state.story_title||'';
  if(draft.timing)state.story_plan_timing=copy(draft.timing);
  delete state.script_plan_draft;
  return added;
}
export function applySelection(state, id, result, basis) {
  if (selectionBasis(state, id) !== basis) throw Error('Shot, library or model settings changed. Materials were not replaced; try again.');
  const current = state.shots.find(s => s.id === id);
  if (!current) throw Error('The target shot was removed.');
  current.refs = copy(result.refs); current.selection_missing = copy(result.missing || []);
  current.selection_timing = result.timing;
}

export function updatePlanIntent(shot, result) {
  const source=shot.plan_source;
  if (!source) return;
  if (result.planned_intent_retained && source.brief_basis===shot.brief &&
      (source.dialogue_basis??shot.dialogue??'')===(shot.dialogue||'')) {
    source.brief_basis=result.description;
    source.dialogue_basis=typeof result.dialogue==='string'?result.dialogue:(shot.dialogue||'');
  } else delete source.brief_basis;
}

export async function readSkillFiles(fileList, directory = false) {
  const files = [...fileList].filter(f => f.name.toLowerCase().endsWith('.md'));
  if (!files.length || files.length > 64 || files.reduce((n,f) => n+f.size, 0) > 262144)
    throw Error('Choose 1–64 Markdown files, at most 256 KiB in total.');
  const contents = {};
  for (const file of files) {
    const name = directory ? file.webkitRelativePath.split('/').slice(1).join('/') : 'SKILL.md';
    if (Object.hasOwn(contents,name)) throw Error('Duplicate Markdown path.');
    contents[name] = new TextDecoder('utf-8', {fatal:true}).decode(await file.arrayBuffer());
  }
  if (!Object.hasOwn(contents,'SKILL.md')) throw Error('Select the folder containing SKILL.md directly.');
  const profile = Object.keys(contents).includes('profiles/baseline.md') ? 'profiles/baseline.md' : '';
  return {name: directory ? files[0].webkitRelativePath.split('/')[0] : files[0].name,
    entrypoint:'SKILL.md', files:contents, profile};
}
