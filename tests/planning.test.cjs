const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const load=()=>import('data:text/javascript;base64,'+fs.readFileSync(path.join(__dirname,'../web/planning.js')).toString('base64'));

test('story-first review replaces the storyboard only and rejects changed story or asset facts',async()=>{
  const {appendPlan,storyPlanBasis}=await load();
  const state={rough_idea:'A lonely afternoon.',assets:[{id:'scene',description:'Counter stools'}],shots:[{id:'old'}]};
  const draft={input_mode:'story',source_kind:'model_authored_from_story',basis:storyPlanBasis(state),title:'Company',shots:[{shot_key:'a',title:'Stay',brief:'She stays.',duration_s:5,source_excerpt:'Model-authored scene',continuity:{mode:'off'}}]};
  state.assets[0].description='Different scene';assert.throws(()=>appendPlan(state,draft,()=> 'new'),/changed/);assert.equal(state.shots[0].id,'old');
  state.assets[0].description='Counter stools';appendPlan(state,draft,()=> 'new');assert.equal(state.shots.length,1);assert.equal(state.shots[0].id,'new');assert.equal(state.shots[0].plan_source.source_kind,'model_authored_from_story');assert.equal(state.story_title,'Company');
});

test('optional storyboard application preserves library, clears old director and blocks in-flight replacement',async()=>{
  const {applyStoryboard}=await load();
  const original={assets:[{id:'old',name:'Keep'}],shots:[{id:'manual'}],director_skill:{name:'Old'},llm_config:{text_model:'Keep provider'}};
  const packet={schema:'shot-storyboard/1',revision:'v1',workspace:{version:1,assets:[{id:'new',name:'New'}],shots:[{id:'planned',refs:[{asset_id:'new'}]}],active_shot_id:'planned'}};
  const result=applyStoryboard(original,packet);
  assert.equal(original.shots[0].id,'manual');assert.equal(result.shots[0].id,'planned');assert.equal(result.assets.length,2);
  assert.equal(result.director_skill,undefined);assert.equal(result.llm_config.text_model,'Keep provider');assert.equal(result.storyboard_source_revision,'v1');
  assert.throws(()=>applyStoryboard({...original,shots:[{job:{status:'running'}}]},packet),/Finish generation/);
  assert.throws(()=>applyStoryboard({...original,assets:[{id:'new',name:'Different'}]},packet),/conflict/);
});

test('skill import keeps folder-relative files and selects only baseline by default',async()=>{
  const {readSkillFiles}=await load();
  const file=(name,content)=>({name:name.split('/').at(-1),webkitRelativePath:'director/'+name,size:content.length,arrayBuffer:async()=>new TextEncoder().encode(content).buffer});
  const bundle=await readSkillFiles([file('SKILL.md','Read [rules](references/shared.md).'),file('references/shared.md','Rule'),file('profiles/baseline.md','Neutral')],true);
  assert.equal(bundle.profile,'profiles/baseline.md');assert.equal(bundle.files['references/shared.md'],'Rule');
  await assert.rejects(()=>readSkillFiles([file('references/shared.md','Rule')],true),/SKILL.md/);
});

test('appending a draft preserves existing shots and maps predecessor IDs',async()=>{
  const {appendPlan,planBasis}=await load();
  const state={script:'Story',shots:[{id:'old',brief:'Keep me'}],director_skill:null};
  const draft={basis:planBasis(state),shots:[{shot_key:'a',title:'A',brief:'First',continuity:{mode:'off'}},{shot_key:'b',title:'B',brief:'Second',continuity:{mode:'continue',source_shot_key:'a'}}]};
  let n=0;appendPlan(state,draft,()=>`new${++n}`);
  assert.equal(state.shots[0].brief,'Keep me');assert.equal(state.shots.length,3);
  assert.equal(state.shots[2].continuity.source_shot_id,'new1');
  assert.deepEqual(state.shots[1].refs,[]);assert.equal(state.active_shot_id,'new1');
  assert.equal(state.shots[1].prompt_sections,undefined);
});

test('planning intent survives append with a frozen brief basis',async()=>{
  const {appendPlan,planBasis}=await load();
  const state={script:'Story',shots:[]};
  const beat={event_keys:['e1'],start_state:'Waiting',change:'B stays',end_state:'Together',cut_reason:'Show decision'};
  const events=[{event_key:'e1',source_excerpt:'Story',decision:'B stays'}];
  const draft={basis:planBasis(state),story_events:events,shots:[{shot_key:'a',title:'A',brief:'B stays',source_excerpt:'Story',dramatic_beat:beat,continuity:{mode:'off'}}]};
  appendPlan(state,draft,()=> 'new');
  assert.deepEqual(state.shots[0].plan_source.dramatic_beat,beat);
  assert.deepEqual(state.shots[0].plan_source.story_events,events);
  assert.equal(state.shots[0].plan_source.brief_basis,'B stays');
  events[0].decision='Changed';assert.equal(state.shots[0].plan_source.story_events[0].decision,'B stays');
});

test('adding a reviewed plan preserves its timing receipt after the preview closes',async()=>{
  const {appendPlan,planBasis}=await load();
  const state={script:'Story',shots:[]};
  const timing={stage:'script_plan',model:'local',total_ms:1250,calls:[]};
  const draft={basis:planBasis(state),timing,shots:[{shot_key:'a',title:'A',brief:'First',continuity:{mode:'off'}}]};
  state.script_plan_draft=draft;appendPlan(state,draft,()=> 'new');
  assert.equal(state.script_plan_draft,undefined);
  assert.deepEqual(state.story_plan_timing,timing);
});

test('explicit refinement amendment invalidates old intent for later refinements',async()=>{
  const {updatePlanIntent}=await load();
  const shot={brief:'B stays',dialogue:'',plan_source:{brief_basis:'B stays',dialogue_basis:'',story_events:[{decision:'Stay'}]}};
  updatePlanIntent(shot,{description:'B remains beside A',dialogue:'',planned_intent_retained:true});
  assert.equal(shot.plan_source.brief_basis,'B remains beside A');
  shot.brief='B remains beside A';
  updatePlanIntent(shot,{description:'B leaves',dialogue:'',planned_intent_retained:false});
  assert.equal(shot.plan_source.brief_basis,undefined);
  shot.brief='B leaves';
  updatePlanIntent(shot,{description:'B leaves in a wide shot',dialogue:'',planned_intent_retained:true});
  assert.equal(shot.plan_source.brief_basis,undefined);
});

test('stale script draft cannot append and stale casting cannot overwrite',async()=>{
  const {appendPlan,planBasis,selectionBasis,applySelection}=await load();
  const state={script:'Story',assets:[{id:'a',description:'Face'}],shots:[{id:'one',brief:'Old',refs:[]} ]};
  const draft={basis:planBasis(state),shots:[]};state.script='New';
  assert.throws(()=>appendPlan(state,draft,()=>''),/changed/i);assert.equal(state.shots.length,1);
  const basis=selectionBasis(state,'one');state.assets[0].description='Changed';
  assert.throws(()=>applySelection(state,'one',{refs:[{asset_id:'a'}]},basis),/changed/i);
  assert.deepEqual(state.shots[0].refs,[]);
});

test('casting affects only the target shot and keeps an accepted prompt stale',async()=>{
  const {selectionBasis,applySelection}=await load();
  const state={assets:[{id:'a',description:'Face'}],shots:[{id:'one',brief:'A',refs:[],prompt_sections:{summary:'Old'},prompt_basis:{old:true}},{id:'two',refs:[]}]};
  applySelection(state,'one',{refs:[{asset_id:'a',role:'reference',notes:'Identity'}],missing:['Cup']},selectionBasis(state,'one'));
  assert.equal(state.shots[0].refs[0].asset_id,'a');assert.deepEqual(state.shots[1].refs,[]);
  assert.equal(state.shots[0].prompt_sections.summary,'Old');assert.deepEqual(state.shots[0].selection_missing,['Cup']);
});

test('director toggle preserves imported package and invalidates effective plan basis',async()=>{
  const {activeDirectorSkill,planBasis}=await load();
  const state={script:'Original',director_skill:{name:'Imported',profile:'a'}};
  assert.equal(activeDirectorSkill(state),state.director_skill);
  const enabled=planBasis(state);state.director_skill_enabled=false;
  assert.equal(activeDirectorSkill(state),null);assert.notEqual(planBasis(state),enabled);
  const disabled=planBasis(state);state.director_skill.profile='b';assert.equal(planBasis(state),disabled);
  assert.equal(state.director_skill.name,'Imported');
});
test('developed story stays reviewable and cannot replace a changed source or shots',async()=>{
  const {developmentBasis,acceptDevelopment,storeDevelopment}=await load();
  const state={rough_idea:'A reunion',script:'Original',shots:[{id:'old',brief:'Keep'}]};
  const basis=developmentBasis(state),result={title:'Reunion',script:'New story',timing:{total_ms:10}};
  storeDevelopment(state,result,basis);assert.equal(state.script,'Original');
  state.script='Typed while waiting';assert.throws(()=>acceptDevelopment(state),/changed/i);
  assert.equal(state.script,'Typed while waiting');assert.equal(state.shots[0].brief,'Keep');
  assert.throws(()=>storeDevelopment(state,result,basis),/changed/i);
  storeDevelopment(state,result,developmentBasis(state));acceptDevelopment(state);
  assert.equal(state.script,'New story');assert.equal(state.shots.length,1);assert.equal(state.story_draft,undefined);
});

test('timing summary distinguishes request wall time from provider decode speed',async()=>{
  const {timingSummary}=await load();
  assert.match(timingSummary({total_ms:2300,model:'local',calls:[{provider_timings:{predicted_per_second:18.75}},{provider_timings:{}}]}),/2.30 s wall.*local.*1 retries.*18.75 tok\/s/);
  assert.match(timingSummary({total_ms:100,calls:[]}),/decode TPS unavailable/);
});

test('changing scene target invalidates development without changing fixed script planning',async()=>{
  const {developmentBasis,storeDevelopment,acceptDevelopment,planBasis}=await load();
  const state={rough_idea:'A reunion',script:'Fixed source',shots:[]};
  const basis=developmentBasis(state),plan=planBasis(state);
  storeDevelopment(state,{script:'Forty second scene'},basis);
  state.story_target_duration_s=60;
  assert.notEqual(developmentBasis(state),basis);assert.equal(planBasis(state),plan);
  assert.throws(()=>acceptDevelopment(state),/changed/i);
  assert.throws(()=>storeDevelopment(state,{script:'Late forty second scene'},basis),/changed/i);
  assert.equal(state.script,'Fixed source');
});
