import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyStoryboard, profileLabel, timingSummary, activeDirectorSkill, planBasis, storyPlanBasis, selectionBasis, appendPlan, applySelection, readSkillFiles, updatePlanIntent } from "./planning.js";

const KEYS = ["subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music"];
const SECTION_NAMES = ["Subject definitions", "Summary", "Continuity notes", "Action and camera", "Sound", "Music"];
const uid = () => {
  if (typeof globalThis.crypto?.randomUUID === "function") return globalThis.crypto.randomUUID();
  // randomUUID requires a secure context; getRandomValues also works on LAN/Tailscale HTTP.
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};
const clone = (v) => JSON.parse(JSON.stringify(v));
const fresh = (n) => ({ id: uid(), title: `Shot ${n}`, brief: "", duration_s: 5, width: 704, height: 480, refs: [] });

function basis(state, shot) {
  return { title: shot.title || "", brief: shot.brief || "", duration_s: Number(shot.duration_s), width: Number(shot.width), height: Number(shot.height),
    references: shot.refs.map((r, i) => {
      const a = state.assets.find((a) => a.id === r.asset_id);
      if (!a) throw Error("A selected asset is missing.");
      return { picture_index: i + 1, asset_id: a.id, name: a.name || "", image: a.image || "", description: a.description || "", role: r.role || "reference", binding_notes: r.notes || "" };
    }), continuity: shot.continuity || { mode: "off" }, ...(shot.dialogue?{dialogue:shot.dialogue}:{}) };
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
function button(text, action, className = "") {
  const el = element("button", className, text); el.type = "button"; el.onclick = action; return el;
}
function field(parent, label, value, onInput, opts = {}) {
  const wrap = element("label", "sw-field"); wrap.append(element("span", "", label));
  const input = element(opts.area ? "textarea" : "input");
  input.setAttribute("aria-label", label);
  if (!opts.area) input.type = opts.type || "text";
  if (opts.rows) input.rows = opts.rows;
  for (const key of ["min", "max", "step", "placeholder"]) if (opts[key] !== undefined) input[key] = opts[key];
  input.value = value ?? "";
  input.oninput = () => onInput(opts.type === "number" ? Number(input.value) : input.value);
  wrap.append(input); parent.append(wrap); return input;
}
function imageUrl(name) {
  const match = /^(.*?)(?:\s+\[(input|output|temp)\])?$/.exec(name);
  const path = (match?.[1] || name).replaceAll("\\", "/");
  const i = path.lastIndexOf("/");
  return api.apiURL(`/view?${new URLSearchParams({ filename: path.slice(i + 1), subfolder: path.slice(0, Math.max(0, i)), type: match?.[2] || "input" })}`);
}

const STAGES = { analyse: "image_analysis", refine: "description_refine", write: "prompt_write" };
const STAGE_NAMES = { analyse: "Image analysis", refine: "Description refinement", write: "Prompt writing" };
function latestTiming(current, operation) {
  return current.last_attempts?.[operation] || current.timings?.findLast(t => t.stage === STAGES[operation]);
}
const timingText = timingSummary;

function mount(node, widget, storyboardMode=false) {
  const root = element("div", storyboardMode?'sw-root sw-storyboard':'sw-root');
  let state, error = "", importing = false, busy = "", busyStarted = 0, timer = null, analysingAssetId = null;
  let busyOperation = null, busyShotId = null;
  let referenceFeedback = null, pendingReferenceFocus = null;
  function operationError(parent, current, operation) {
    const attempt = current.last_attempts?.[operation];
    if (attempt?.status !== 'failed' || !attempt.message || (busyOperation === operation && busyShotId === current.id)) return;
    const message = element('p', 'sw-error sw-operation-error', attempt.message);
    message.setAttribute('role', 'alert');parent.append(message);
  }
  function timingBadge(operation, timing, assetId = null) {
    const running = busyOperation === operation && (assetId ? analysingAssetId === assetId : busyShotId === shot().id);
    const badge = element('span', 'sw-operation-time', running ? `Running · ${((performance.now() - busyStarted) / 1000).toFixed(1)} s` : timingText(timing));
    badge.dataset.state = running ? 'running' : timing?.status === 'failed' ? 'failed' : timing ? 'completed' : 'empty';
    badge.setAttribute('aria-label', `${STAGE_NAMES[operation]} elapsed time`);
    badge.title = running ? 'Elapsed request time' : timing ? `Model operation time, including retries. ${timing.model || timing.calls?.[0]?.model || ''}`.trim() : 'Elapsed time appears here after this operation.';
    return badge;
  }
  function updateProgress() {
    const elapsed = ((performance.now() - busyStarted) / 1000).toFixed(1);
    const label = root.querySelector('.sw-busy');
    if (label) label.textContent = `${busy} · ${elapsed} s`;
    for (const badge of root.querySelectorAll('.sw-operation-time[data-state="running"]')) badge.textContent = `Running · ${elapsed} s`;
  }
  const defaultConfig = {base_url:"http://127.0.0.1:1234/v1",text_model:"",vision_model:"",api_key_env:"",timeout_s:300,unload_url:"",unload_before_generation:false};
  const polling=new Set();
  let connectionTest = null;
  let planningOpen = true;
  async function planScript() {
    if (busy) return;
    const captured = clone(state), basis = planBasis(captured), canvas = captured.shots.find(s=>s.id===captured.active_shot_id);
    busy = 'Planning all shots';busyStarted = performance.now();error = '';render();timer = setInterval(updateProgress,200);
    try {
      const result = await post('/shot-workspace/llm/plan', {script:captured.script,
        director_skill:activeDirectorSkill(captured), config:captured.llm_config || defaultConfig});
      if (!node.graph) return;
      if (planBasis(state) !== basis) throw Error('Script, skill or model settings changed. The plan was not applied.');
      state.script_plan_draft = {...result,basis,width:canvas?.width??704,height:canvas?.height??480};save();
    } catch (cause) {error = cause.message;}
    finally {clearInterval(timer);busy = '';render();}
  }
  async function planStory() {
    if(busy)return;
    const captured=clone(state),basis=storyPlanBasis(captured);
    busy='Planning your story';busyStarted=performance.now();error='';render();timer=setInterval(updateProgress,200);
    try{
      const result=await post('/shot-workspace/llm/story-plan',{story:captured.rough_idea,target_duration_s:captured.story_target_duration_s??40,assets:captured.assets,director_skill:activeDirectorSkill(captured),config:captured.llm_config||defaultConfig});
      if(!node.graph)return;
      if(storyPlanBasis(state)!==basis)throw Error('Story, duration, director or model settings changed. Plan again.');
      state.script_plan_draft={...result,basis,input_mode:'story',width:captured.shots[0]?.width??704,height:captured.shots[0]?.height??480};save();
    }catch(cause){error=cause.message;}
    finally{clearInterval(timer);busy='';render();}
  }
  async function selectMaterials() {
    if (busy) return;
    const captured = clone(state), id = shot().id, basis = selectionBasis(captured,id);
    busy = 'Selecting materials';busyStarted = performance.now();error = '';render();timer = setInterval(updateProgress,200);
    try {
      const result = await post('/shot-workspace/llm/select',{workspace:captured,config:captured.llm_config || defaultConfig});
      if (!node.graph) return;
      applySelection(state,id,result,basis);referenceFeedback={shotId:id,text:`Selected ${result.refs.length} materials for this shot.`};save();
    } catch (cause) {error = cause.message;}
    finally {clearInterval(timer);busy = '';render();}
  }
  async function post(path, body) {
    const response = await api.fetchApi(path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const value = await response.json();
    if (!response.ok) throw Error(value.error || `Request failed (${response.status})`);
    return value;
  }
  function fingerprint(value, id, operation) {
    const index=value.shots.findIndex(s=>s.id===id);
    const sourceId=value.shots[index].continuity?.source_shot_id;
    const previous=sourceId?value.shots.find(s=>s.id===sourceId):value.shots[index-1];
    return JSON.stringify([basis(value,value.shots[index]),value.shots[index].dialogue||"",previous?.brief||"",operation==='refine'?[activeDirectorSkill(value),value.shots[index].plan_source]:null]);
  }
  async function testConnection() {
    if(busy)return;
    const config=clone(state.llm_config||defaultConfig);
    busy='Testing LLM connection';connectionTest={status:'running'};render();
    try{
      const result=await post('/shot-workspace/llm/test',{config});
      if(JSON.stringify(config)!==JSON.stringify(state.llm_config))throw Error('Connection settings changed. Test again.');
      connectionTest={status:'success',result};
    }catch(cause){connectionTest={status:'error',message:cause.message};}
    finally{busy='';render();}
  }
  async function author(operation, asset = null) {
    if(busy) return;
    const captured=clone(state), id=shot().id;
    captured.director_skill=activeDirectorSkill(captured);
    const original=asset?JSON.stringify([asset.name,asset.image,asset.description]):fingerprint(captured,id,operation);
    busy=operation==="analyse"?"Reading image":operation==="refine"?"Refining description":"Writing H3 prompt";
    analysingAssetId=asset?.id || null;
    if(asset)delete asset.analysis_error;
    busyOperation=operation;busyShotId=id;busyStarted=performance.now();error="";render();
    timer=setInterval(updateProgress,200);
    try {
      const result=await post(`/shot-workspace/llm/${operation}`,{workspace:captured,asset:asset?clone(asset):undefined,config:state.llm_config||defaultConfig,request:shot().refine_request||""});
      if(!node.graph) return;
      if(asset){
        const current=state.assets.find(a=>a.id===asset.id);
        if(!current) throw Error("Asset removed while analysing. Result was not applied.");
        current.analysis_timing=result.timing;
        current.analysis_attempt={...result.timing,status:'completed'};
        if(JSON.stringify([current.name,current.image,current.description])!==original)throw Error("Asset changed while analysing. Description was kept.");
        current.analysis_suggestion=result.description;current.analysis_content_sha256=result.content_sha256;
        delete current.analysis_error;
      }else{
        const current=state.shots.find(s=>s.id===id);
        if(!current)throw Error("Shot removed while writing. Result was not applied.");
        (current.timings ||= []).push(result.timing);
        (current.last_attempts ||= {})[operation]={...result.timing,status:'completed'};
        if(fingerprint(state,id,operation)!==original)throw Error("Shot, director skill or reference context changed while writing. Previous draft/prompt was kept.");
        if(operation==="refine"){
          updatePlanIntent(current,result);
          current.before_description=current.brief;current.brief=result.description;
          if(typeof result.dialogue==='string')current.dialogue=result.dialogue;
        }else{
          current.prompt_sections=result.prompt_sections;current.prompt_basis=result.prompt_basis;
          current.prompt_editor_dirty=false;current.prompt_origin="llm";
          current.prompt_draft=JSON.stringify(result.prompt_sections,null,2);
        }
      }
      save();
    }catch(cause){
      error=cause.message;
      const attempt={stage:STAGES[operation],total_ms:performance.now()-busyStarted,status:'failed',message:error};
      if(asset){const current=state.assets.find(a=>a.id===asset.id);if(current){current.analysis_error=error;current.analysis_attempt=attempt;error='';}}
      else {const current=state.shots.find(s=>s.id===id);if(current){(current.last_attempts ||= {})[operation]=attempt;error='';}}
      save();
    }
    finally{clearInterval(timer);busy="";analysingAssetId=null;busyOperation=null;busyShotId=null;render();}
  }
  async function generate() {
    if(busy)return;
    busy="Submitting shot";error="";render();
    try{
      const captured=clone(state);
      const prompt=await app.graphToPrompt();
      const receipt=await post('/shot-workspace/jobs',{node_id:String(node.id),workspace:captured,prompt:prompt.output});
      const target=state.shots.find(s=>s.id===receipt.shot_id);
      target.job=receipt;save();
      startPoll(receipt.prompt_id,receipt.shot_id);
    }catch(cause){error=cause.message;}
    finally{busy="";render();}
  }
  function startPoll(jobId,shotId){if(polling.has(jobId))return;polling.add(jobId);poll(jobId,shotId);}
  async function poll(jobId,shotId){
    try{
      const response=await api.fetchApi(`/shot-workspace/jobs/${jobId}`);
      if(!response.ok)throw Error('Could not retrieve generation status.');
      const receipt=await response.json();
      if(!node.graph){polling.delete(jobId);return;}
      const target=state.shots.find(s=>s.id===shotId);
      if(!target||target.job?.prompt_id!==jobId){polling.delete(jobId);return;}
      target.job=receipt;save();
      const panel=root.querySelector('.sw-output');
      if(panel)paintOutput(panel,shot());
      if(['queued','running'].includes(receipt.status))setTimeout(()=>poll(jobId,shotId),1500);
      else polling.delete(jobId);
    }catch(cause){error=cause.message;if(node.graph)setTimeout(()=>poll(jobId,shotId),3000);else polling.delete(jobId);}
  }
  function paintOutput(panel,current){
    panel.replaceChildren();
    const job=current.job;
    panel.append(element('h3','sw-panel-title', 'Video output'), element('p','sw-help','Generate with the connected workflow and review this shot’s result.'));
    const prepared=current.prepared_result;
    if(prepared){
      const section=element('section','sw-prepared-result');
      section.append(element('h4','','Prepared result'),element('p','sw-help','Previously rendered clip, supplied with this example. Editing the shot does not change this saved clip.'));
      const file=prepared.file;
      const validFile=file&&['input','output','temp'].includes(file.type)&&typeof file.filename==='string'&&file.filename&&!/[\\/]/.test(file.filename)&&typeof file.subfolder==='string'&&!file.subfolder.split(/[\\/]/).includes('..');
      if(prepared.status==='received'&&validFile){
        if(Number.isInteger(prepared.video_frames)&&prepared.video_frames>0&&Number.isFinite(prepared.fps)&&prepared.fps>0){
          section.append(element('p','sw-help',`${prepared.video_frames} frames · ${prepared.fps} fps · ${(prepared.video_frames/prepared.fps).toFixed(3)} s picture`));
        }
        const video=element('video');video.controls=true;video.preload='metadata';
        video.src=api.apiURL(`/view?${new URLSearchParams({filename:file.filename,subfolder:file.subfolder,type:file.type})}`);
        video.onerror=()=>{if(!section.querySelector('.sw-error'))section.append(element('p','sw-error','Prepared clip could not be loaded. Check that the media was imported.'));};
        section.append(video);
      }else section.append(element('p','sw-help','Prepared media not received. Playback will be available after import.'));
      panel.append(section);
    }
    if(job){
      panel.append(element('p','sw-help',`${job.status} · ${job.generation_ms?`${(job.generation_ms/1000).toFixed(1)}s`:'Timing pending'} · ${job.shot_id}`));
      panel.append(element('p','sw-help',job.continuation||''));
      if(job.error)panel.append(element('p','sw-error',job.error));
      for(const file of job.outputs||[]){
        const video=element('video');video.controls=true;video.preload='metadata';
        const duration=element('p','sw-help sw-delivered-duration','Delivered video duration: reading file…');
        video.onloadedmetadata=()=>{duration.textContent=Number.isFinite(video.duration)&&video.duration>0?`Delivered video duration: ${video.duration.toFixed(2)} s`:'Delivered video duration unavailable.';};
        video.onerror=()=>{duration.textContent='Delivered video duration unavailable — video could not be loaded.';};
        video.src=api.apiURL(`/view?${new URLSearchParams(file)}`);panel.append(duration,video);
      }
    }else panel.append(element('p','sw-help','Output is attached to the queued shot and revision. Continuation depends on the connected workflow.'));
    const active=state.shots.some(s=>['queued','running'].includes(s.job?.status));
    const stale=current.prompt_editor_dirty||!current.prompt_basis||JSON.stringify(current.prompt_basis)!==JSON.stringify(basis(state,current));
    const run=button(active?'Generating…':'Generate this shot',generate,'sw-primary sw-generate');
    const unloadLabel=element('label','sw-unload');
    const unload=element('input');unload.type='checkbox';
    unload.checked=state.llm_config?.unload_before_generation===true;
    unload.disabled=!!busy||active;
    unload.onchange=()=>{state.llm_config ||= clone(defaultConfig);state.llm_config.unload_before_generation=unload.checked;save();};
    unloadLabel.append(unload,document.createTextNode('Unload LLM before generation'));
    panel.append(unloadLabel);
    run.disabled=!!busy||active||!current.prompt_sections||stale;panel.append(run);
  }
  function read() {
    try {
      state = JSON.parse(widget.value);
      if (state.version !== 1 || !Array.isArray(state.shots) || !Array.isArray(state.assets)) throw Error("Expected a version 1 workspace with shots and assets.");
    } catch (cause) {
      state = null; root.replaceChildren(element("p", "sw-error", `Workspace could not be loaded: ${cause.message}`));
      const repair = element("textarea"); repair.value = widget.value; repair.rows = 12; repair.setAttribute("aria-label", "Repair workspace JSON");
      root.append(repair, button("Reload repaired JSON", () => { widget.value = repair.value; if (read()) render(); }));
      return false;
    }
    return true;
  }
  function save() {
    widget.value = JSON.stringify(state);
    node.graph?.setDirtyCanvas(true, true);
    node._swRefreshStatus?.();
  }
  function shot() { return state.shots.find((s) => s.id === state.active_shot_id) || state.shots[0]; }
  function mutate(fn, redraw = false) { fn(); save(); if (redraw) render(); }
  function render() {
    if (!state) return;
    const previousScroll = root.querySelector(".sw-editor")?.scrollTop || 0;
    const previousLibraryScroll = root.querySelector(".sw-library-panel")?.scrollTop || 0;
    const promptExpanded = root.querySelector(".sw-prompt-editor")?.open;
    const connectionExpanded = root.querySelector('.sw-connection')?.open;
    const previousSpeech=root.querySelector('.sw-dialogue');
    const speechExpanded=previousSpeech?.dataset.hasDialogue==='true'?previousSpeech.open:undefined;
    const expandedDescriptions = new Set([...root.querySelectorAll('.sw-asset-description[open]')].map(el => el.closest('.sw-asset').dataset.assetId));
    const current = shot(); state.active_shot_id = current?.id??null;
    node._swRefreshStatus=()=>{};
    root.replaceChildren();
    const header = element("header", "sw-header");
    const heading = element("div"); heading.append(element("h2", "", storyboardMode?'Director Storyboard':'Shot workspace'), element("p", "", storyboardMode?'Optional story and director planning for all shots.':'Author here. Generate in the workflow you already use.'));
    header.append(heading, element('span','sw-badge',storyboardMode?'Optional add-on':'Shot authoring')); root.append(header);
    const toolbar = element("div", "sw-toolbar");
    const selector = element("select"); selector.setAttribute("aria-label", "Active shot");
    state.shots.forEach((s, i) => { const opt = element("option", "", `${i + 1}. ${s.title || "Untitled"}`); opt.value = s.id; opt.selected = s.id === current?.id; selector.append(opt); });
    if(!current){selector.append(element('option','','0 shots — plan your story above'));selector.disabled=true;}
    selector.onchange = () => mutate(() => { state.active_shot_id = selector.value; }, true);
    toolbar.append(element('span','sw-shot-scope','Shots'),selector, button("+ Shot", () => mutate(() => {
      const next = fresh(state.shots.length + 1); next.refs = clone(state.shots.at(-1)?.refs||[]); state.shots.push(next); state.active_shot_id = next.id;
    }, true)), button("Remove shot", () => {
      if (!current) return;
      mutate(() => { const i = state.shots.indexOf(current); state.shots.splice(i, 1); state.active_shot_id = state.shots[Math.max(0, i - 1)]?.id??null; }, true);
    }), button("Workflow interface ↗", () => {
      const linked = (node.outputs[0].links || []).map(id => node.graph.links[id]).map(link => node.graph.getNodeById(link.target_id));
      let target = linked.find(n => n?.type === "ShotWorkspaceInterface");
      if (!target) {
        target = LiteGraph.createNode("ShotWorkspaceInterface");
        if (!target) { error = "The Workflow Interface node needs the updated backend. Refresh after it is loaded."; render(); return; }
        target.pos = [node.pos[0] + node.size[0] + 240, node.pos[1] + 140];
        node.graph.add(target); node.connect(0, target, 0);
      }
      app.canvas.selectNode(target); app.canvas.centerOnNode(target);
    }, "sw-interface-action")); root.append(toolbar);
    toolbar.hidden=storyboardMode;
    const scroll = element("div", "sw-scroll"); root.append(scroll);
    const editor = element("main", "sw-editor"); scroll.append(editor);
    const sectionNav=element('nav','sw-section-nav');sectionNav.setAttribute('aria-label','Shot authoring sections');
    const sections=[['References','.sw-reference-panel'],['Description','.sw-shot-panel'],['Prompt','.sw-prompt-panel'],['Output','.sw-output']];
    for(const [label,selector] of sections){
      const jump=button(label,()=>{
        const target=editor.querySelector(selector);if(selector==='.sw-planning'){target.open=true;planningOpen=true;}target?.scrollIntoView({block:'start'});target?.focus({preventScroll:true});
        for(const item of sectionNav.children){if(item.dataset.section===selector)item.setAttribute('aria-current','location');else item.removeAttribute('aria-current');}
      });
      jump.setAttribute('aria-label',`Go to ${label.toLowerCase()}`);jump.dataset.section=selector;sectionNav.append(jump);
    }
    if(!storyboardMode)editor.append(sectionNav);
    if(storyboardMode){
    const planning=element('details','sw-planning sw-panel');planning.open=planningOpen;planning.tabIndex=-1;
    planning.ontoggle=()=>{planningOpen=planning.open;};
    planning.append(element('summary','','Story & direction · All shots'));
    planning.append(element('p','sw-help','Global story and director guidance for the whole shot plan. Apply it to Shot Workspace to edit individual shots.'));
    planning.append(element('p','sw-help','Tell us what you want to film. A few sentences or rough notes are enough — no screenplay or dialogue required.'));
    const ideaInput=field(planning,'Story',state.rough_idea||'',v=>mutate(()=>{state.rough_idea=v;}),{area:true,rows:5,placeholder:'For example: Two neighbors meet during a power outage. One wants to borrow a flashlight; the other is reluctant to admit being afraid of the dark. Light, slightly awkward humor.'});
    ideaInput.maxLength=40000;ideaInput.disabled=!!busy;
    const sceneTarget=field(planning,'Target duration (seconds)',state.story_target_duration_s??40,v=>mutate(()=>{state.story_target_duration_s=Math.min(120,Math.max(5,Number.isFinite(v)?v:40));}),{type:'number',min:5,max:120,step:1});sceneTarget.disabled=!!busy;
    planning.append(element('p','sw-help','The director can propose dialogue where it helps, or keep the shots silent. You review the whole plan before using it.'));
    const skillActions=element('div','sw-actions');
    for (const [label,directory] of [['Import SKILL.md',false],['Import skill folder',true]]) {
      const input=element('input');input.type='file';input.accept='.md';input.hidden=true;
      if(directory){input.webkitdirectory=true;input.multiple=true;}
      input.onchange=async()=>{
        if(busy)return;
        busy='Reading director skill';error='';render();
        try {const skill=await readSkillFiles(input.files,directory);state.director_skill=skill;state.director_skill_enabled=true;save();}
        catch(cause){error=cause.message;}finally{busy='';render();}
      };
      const importButton=button(label,()=>input.click());importButton.disabled=!!busy;skillActions.append(importButton,input);
    }
    planning.append(skillActions);
    const skill=state.director_skill;
    if(skill){
      const mode=element('select');mode.setAttribute('aria-label','Director guidance');
      for(const [value,label] of [['off','No imported director'],['on','Use imported director']]){const option=element('option','',label);option.value=value;option.selected=(activeDirectorSkill(state)?'on':'off')===value;mode.append(option);}
      mode.disabled=!!busy;mode.onchange=()=>mutate(()=>{state.director_skill_enabled=mode.value==='on';},true);planning.append(mode);
      planning.append(element('p','sw-help',`Imported skill: ${skill.name}`));
      const profiles=Object.keys(skill.files).filter(name=>name.startsWith('profiles/'));
      if(profiles.length){
        const profile=element('select');profile.setAttribute('aria-label','Director profile');
        for(const name of ['',...profiles]){const option=element('option','',name?profileLabel(name):'Base skill only');option.value=name;option.selected=name===(skill.profile||'');profile.append(option);}
        profile.disabled=!!busy||!activeDirectorSkill(state);profile.onchange=()=>mutate(()=>{skill.profile=profile.value;});planning.append(profile);
      }
      const remove=button('Remove imported skill',()=>mutate(()=>{delete state.director_skill;},true));remove.disabled=!!busy;planning.append(remove);
    }else planning.append(element('p','sw-help','No imported director. Built-in planning rules apply. Import a skill to compare guidance.'));
    planning.append(element('p','sw-help','Skill folders include linked Markdown references and one selected profile. Text only; no tools or scripts run.'));
    const planButton=button('Plan shots',planStory,'sw-primary');planButton.disabled=!!busy||!state.rough_idea?.trim();
    ideaInput.addEventListener('input',()=>{planButton.disabled=!!busy||!state.rough_idea?.trim();});planning.append(planButton);
    if(busy)planning.append(element('p','sw-help sw-busy',`${busy} · ${((performance.now()-busyStarted)/1000).toFixed(1)} s`));
    const scriptOptions=element('details','sw-existing-script');scriptOptions.append(element('summary','','Have a finished script? (optional)'));
    const scriptInput=field(scriptOptions,'Existing script (optional)',state.script||'',v=>mutate(()=>{state.script=v;}),{area:true,rows:5,placeholder:'Only if you already have a script whose dialogue should stay unchanged.'});scriptInput.maxLength=40000;scriptInput.disabled=!!busy;
    const strictPlan=button('Plan existing script',planScript);strictPlan.disabled=!!busy||!state.script?.trim();scriptInput.addEventListener('input',()=>{strictPlan.disabled=!!busy||!state.script?.trim();});scriptOptions.append(strictPlan);planning.append(scriptOptions);
    if(state.story_plan_timing)planning.append(element('p','sw-help',`Last plan · ${timingText(state.story_plan_timing)}`));
    if(state.script_plan_draft){
      const draft=state.script_plan_draft;
      planning.append(element('p','sw-help',`${draft.shots.length} planned shots · ${timingText(draft.timing)} · References can be selected per shot after adding.`));
      const preview=element('div','sw-plan-preview');
      draft.shots.forEach((s,i)=>{
        const card=element('article','sw-plan-shot');card.append(element('h4','',`${i+1}. ${s.title} · ${s.duration_s}s`),element('p','',s.brief));
        if(s.dialogue)card.append(element('p','sw-help',s.dialogue));
        if(s.dramatic_beat){
          const detail=element('details','sw-help');detail.append(element('summary','','Story beat and framing purpose'));
          for(const [label,key] of [['Starts','start_state'],['Changes','change'],['Ends','end_state'],['View purpose','cut_reason']])detail.append(element('p','',`${label}: ${s.dramatic_beat[key]}`));
          card.append(detail);
        }
        if(s.continuity.mode==='continue')card.append(element('p','sw-help',`Planned continuation from ${s.continuity.source_shot_key} — media must be connected separately.`));
        preview.append(card);
      });planning.append(preview);
      const add=button(draft.input_mode==='story'?`Use this plan (${draft.shots.length} shots)`:`Add all ${draft.shots.length} shots`,()=>{try{appendPlan(state,draft,uid);save();render();}catch(cause){error=cause.message;render();}},'sw-primary');add.disabled=!!busy;planning.append(add);
      const discard=button('Discard draft',()=>mutate(()=>{delete state.script_plan_draft;},true));discard.disabled=!!busy;planning.append(discard);
    }
    if(state.shots.length){
      const reviewed=element('section','sw-reviewed-shots');reviewed.append(element('h4','',`Reviewed storyboard · ${state.shots.length} shots`));
      state.shots.forEach((s,i)=>{const row=element('details');row.append(element('summary','',`${i+1}. ${s.title||'Untitled'} · ${Number(s.duration_s).toFixed(2)}s`),element('p','sw-help',s.brief||''));if(s.dialogue)row.append(element('p','sw-story-text',s.dialogue));reviewed.append(row);});planning.append(reviewed);
    }
    root.insertBefore(planning,toolbar);
    }
    if(current)editor.append(element('h3','sw-current-shot-heading',`Current shot · ${current.title||'Untitled'}`));
    const connection=element('details','sw-connection');connection.append(element('summary','', `LLM connection / settings · ${state.llm_config?.text_model||'Select writing model'}`));
    connection.open=!!connectionExpanded;
    state.llm_config ||= clone(defaultConfig);
    for(const [key,label]of [['base_url','OpenAI-compatible URL'],['text_model','Writing model'],['vision_model','Vision model'],['api_key_env','API key environment variable'],['unload_url','Model unload URL before video (optional)']]){
      field(connection,label,state.llm_config[key],v=>mutate(()=>{state.llm_config[key]=v;connectionTest=null;root.querySelector('.sw-connection-status')?.remove();}));
    }
    connection.append(button(connectionTest?.status==='running'?'Testing…':'Test connection',testConnection));
    if(connectionTest){
      const text=connectionTest.status==='running'?'Checking text and vision requests…':connectionTest.status==='error'?connectionTest.message:
        `Connected · Text: ${connectionTest.result.text.model} · Vision: ${connectionTest.result.vision.model} · Both requests passed.`;
      const status=element('p',`sw-connection-status ${connectionTest.status==='error'?'sw-error':'sw-help'}`,text);
      status.setAttribute('role',connectionTest.status==='error'?'alert':'status');connection.append(status);
    }
    const extraMedia = button('Advanced media ports',()=>{
      const target=LiteGraph.createNode('ShotWorkspaceMedia');
      if(!target){error='Reload ComfyUI after enabling the updated node package.';render();return;}
      target.pos=[node.pos[0]+node.size[0]+80,node.pos[1]];node.graph.add(target);node.connect(0,target,0);
    });scroll.append(connection);
    if(storyboardMode){
      editor.remove();
      const transfer=element('section','sw-storyboard-transfer');
      transfer.append(element('p','sw-help',`${state.shots.length} reviewed shots. Connect storyboard → Shot Workspace, then apply. This replaces the receiving shot list; it does not run a model or generate video.`));
      const apply=button('Apply storyboard to connected workspace',async()=>{
        try{
          const targets=(node.outputs[0].links||[]).map(id=>node.graph.links[id]).map(link=>node.graph.getNodeById(link.target_id)).filter(n=>n?.type==='ShotWorkspace');
          if(targets.length!==1)throw Error('Connect this storyboard to exactly one Shot Workspace before applying.');
          if(!targets[0]._swApplyStoryboard)throw Error('Refresh the receiving workspace before applying.');
          const captured=clone(state),before=JSON.stringify(captured);
          const packet=await post('/shot-workspace/storyboard',{workspace:captured});
          if(JSON.stringify(state)!==before)throw Error('Storyboard changed during transfer. Review and apply again.');
          if(!(node.outputs[0].links||[]).some(id=>node.graph.links[id]?.target_id===targets[0].id))throw Error('Storyboard connection changed. Connect and apply again.');
          targets[0]._swApplyStoryboard(packet);error='';
          transfer.querySelector('[role="status"]').textContent=`Applied ${packet.workspace.shots.length} shots to the connected workspace.`;
        }catch(cause){error=cause.message;render();}
      },'sw-primary');apply.disabled=!!busy||!state.shots.length;
      transfer.append(apply,element('p','sw-help',''));transfer.lastChild.setAttribute('role','status');
      if(error)transfer.append(element('p','sw-error',error));
      root.append(transfer);
      if(busy)root.querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=true);
      return;
    }
    if(!current){
      editor.append(element('section','sw-empty-shots','0 shots. Add a storyboard upstream, or use + Shot to create a shot manually.'));
      if(error)editor.append(element('p','sw-error',error));
      if(busy)root.querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=true);
      return;
    }
    const references=element('section','sw-panel sw-reference-panel');editor.append(references);
    const referenceHeader=element('div','sw-section-header');referenceHeader.append(element('h3','sw-panel-title','Shot references'),element('span','sw-reference-count',`${current.refs.length} / 9 pictures`));
    references.append(referenceHeader,element('p','sw-help','These pictures are sent in this order. The assistant determines how to use each picture from its description and your brief.'));
    const autoSelect=button('Auto-select materials',selectMaterials);autoSelect.disabled=!!busy||!current.brief?.trim();
    references.append(autoSelect,element('p','sw-help','Uses saved material descriptions and this shot’s description. Replaces this shot’s selection; library files are kept.'));
    if(current.selection_timing)references.append(element('p','sw-help',`Material selection · ${timingText(current.selection_timing)}`));
    if(current.selection_missing?.length)references.append(element('p','sw-error',`Missing materials: ${current.selection_missing.join('; ')}`));
    const feedback=element('p','sw-reference-feedback',referenceFeedback?.shotId===current.id?referenceFeedback.text:'');
    feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');references.append(feedback);
    const referenceList=element('ol','sw-references');referenceList.setAttribute('aria-label','Pictures for this shot');referenceList.tabIndex=0;references.append(referenceList);
    if(!current.refs.length)references.append(element('p','sw-reference-empty','No pictures selected. Choose “Use in this shot” in the asset library.'));
    current.refs.forEach((ref,index)=>{
      const asset=state.assets.find(a=>a.id===ref.asset_id);if(!asset)return;
      const row=element('li','sw-reference');row.dataset.assetId=asset.id;row.tabIndex=-1;
      const picture=element('img');picture.src=imageUrl(asset.image);picture.alt=asset.name;picture.loading='lazy';
      const content=element('div','sw-reference-content');
      const title=element('div','sw-reference-title');const name=element('span','sw-reference-name',asset.name);name.title=asset.name;title.append(element('strong','sw-picture-number',`Picture ${index+1}`),name);content.append(title);
      const controls=element('div','sw-reference-actions');
      for(const [delta,label,symbol] of [[-1,'earlier','←'],[1,'later','→']]){
        const move=button(symbol,()=>mutate(()=>{
          const target=index+delta;[current.refs[index],current.refs[target]]=[current.refs[target],current.refs[index]];
          referenceFeedback={shotId:current.id,text:`${asset.name} is now Picture ${target+1}.`};pendingReferenceFocus={assetId:asset.id,direction:label};
        },true));
        move.dataset.direction=label;
        move.setAttribute('aria-label',`Move Picture ${index+1} ${label}`);move.title=`Move Picture ${index+1} ${label}`;move.disabled=index+delta<0||index+delta>=current.refs.length;controls.append(move);
      }
      const remove=button('Remove',()=>mutate(()=>{
        current.refs.splice(index,1);referenceFeedback={shotId:current.id,text:`${asset.name} removed from this shot. It stays in the asset library.`};
        pendingReferenceFocus={assetId:(current.refs[index]||current.refs[index-1])?.asset_id};
      },true));remove.setAttribute('aria-label',`Remove Picture ${index+1}`);controls.append(remove);
      row.append(picture,content,controls);referenceList.append(row);
    });
    const referenceWarning=element('p','sw-reference-warning');referenceWarning.hidden=true;references.append(referenceWarning);
    const shotPanel=element('section','sw-panel sw-shot-panel');
    shotPanel.append(element('h3','sw-panel-title','Shot description'),element('p','sw-help','Describe the action and camera intent. Refine the idea before writing the prompt.'));
    if(activeDirectorSkill(state))shotPanel.append(element('p','sw-help',`Director guidance: ${state.director_skill.profile?profileLabel(state.director_skill.profile):state.director_skill.name}.`));
    if(busy)shotPanel.append(element('p','sw-busy',busy));
    editor.append(shotPanel);
    const summary = element("div", "sw-summary");
    field(summary, "Title", current.title, (v) => mutate(() => { current.title = v; selector.selectedOptions[0].textContent = `${state.shots.indexOf(current) + 1}. ${v}`; }));
    const numbers = element("div", "sw-numbers");
    field(numbers, "Sampling duration (s)", current.duration_s, (v) => mutate(() => current.duration_s = v), { type: "number", min: 0.1, max: 120, step: 0.1 });
    field(numbers, "Width", current.width, (v) => mutate(() => current.width = v), { type: "number", min: 32, max: 16384, step: 32 });
    field(numbers, "Height", current.height, (v) => mutate(() => current.height = v), { type: "number", min: 32, max: 16384, step: 32 });
    summary.append(numbers); shotPanel.append(summary);
    shotPanel.append(element('p','sw-help sw-duration-help','Model input before workflow trimming. Motion Context removes overlap; the delivered video’s measured duration appears with its result.'));
    field(shotPanel, "Shot brief", current.brief, (v) => mutate(() => current.brief = v), { area: true, rows: 5, placeholder: "What happens in this shot? Describe the action and camera intent." });
    const assist=element('div','sw-actions');
    assist.append(button('Refine description',()=>author('refine')),timingBadge('refine',latestTiming(current,'refine')));
    if(current.before_description!==undefined)assist.append(button('Undo description',()=>mutate(()=>{[current.brief,current.before_description]=[current.before_description,current.brief];},true)));
    shotPanel.append(assist);
    operationError(shotPanel,current,'refine');
    field(shotPanel,'Refinement request (optional)',current.refine_request||'',v=>mutate(()=>current.refine_request=v),{placeholder:'For example: keep the camera locked and make the action slower.'});
    const speech=element('details','sw-dialogue');speech.dataset.hasDialogue=String(!!current.dialogue);speech.open=speechExpanded??!!current.dialogue;speech.append(element('summary','','Dialogue (optional)'));
    field(speech,'Exact dialogue cues',current.dialogue||'',v=>mutate(()=>current.dialogue=v),{area:true,rows:2,placeholder:'Speaker [Language]: exact words'});shotPanel.append(speech);
    const libraryPanel=element('section','sw-panel sw-library-panel');scroll.append(libraryPanel);
    const assetsHeader = element("div", "sw-section-header"); assetsHeader.append(element("h3", "", `Asset library (${state.assets.length})`));
    const picker = element("input"); picker.type = "file"; picker.accept = "image/png,image/jpeg,image/webp"; picker.multiple = true; picker.hidden = true;
    const upload = button(importing ? "Uploading…" : "+ Images", () => picker.click()); upload.disabled = importing;
    picker.onchange = async () => {
      importing = true; error = ""; render();
      try {
        for (const file of picker.files) {
          const form = new FormData(); form.append("image", file); form.append("type", "input"); form.append("subfolder", "shot_workspace");
          const response = await api.fetchApi("/upload/image", { method: "POST", body: form });
          if (!response.ok) throw Error(`Image upload failed (${response.status}).`);
          const result = await response.json();
          state.assets.push({ id: uid(), name: file.name.replace(/\.[^.]+$/, ""), image: [result.subfolder, result.name].filter(Boolean).join("/"), description: "" }); save();
        }
      } catch (cause) { error = cause.message; }
      finally { importing = false; render(); }
    };
    assetsHeader.append(upload, picker); libraryPanel.append(assetsHeader);
    libraryPanel.append(element("p", "sw-help", "Reusable images and descriptions. Add pictures to the current shot, then arrange their order in Shot references."));
    const library = element("div", "sw-library");
    if (!state.assets.length) library.append(element("p", "sw-empty", "Add images to start your reference library."));
    for (const asset of state.assets) {
      const refIndex = current.refs.findIndex((r) => r.asset_id === asset.id), selected = refIndex >= 0;
      const card = element("article", `sw-asset${selected ? " selected" : ""}`);
      card.dataset.assetId = asset.id;
      const top = element("div", "sw-asset-top"), image = element("img"); image.src = imageUrl(asset.image); image.alt = asset.name; image.loading = "lazy";
      top.append(image);
      const fields = element("div", "sw-asset-fields");
      field(fields, "Asset name", asset.name, (v) => {
        mutate(() => asset.name = v);image.alt=v;
        const reference=[...root.querySelectorAll('.sw-reference')].find(el=>el.dataset.assetId===asset.id);
        if(reference){reference.querySelector('.sw-reference-name').textContent=v;reference.querySelector('.sw-reference-name').title=v;reference.querySelector('img').alt=v;}
      });
      fields.append(button(selected ? `✓ Picture ${refIndex + 1}` : "Use in this shot", () => mutate(() => {
        if (current.refs.length >= 9) { error = "H3 accepts at most 9 image references."; return; } current.refs.push({ asset_id: asset.id, role: "reference", notes: "" });
        referenceFeedback={shotId:current.id,text:`${asset.name} added as Picture ${current.refs.length}.`};
      }, true), selected ? "sw-selected" : ""));
      if(selected)fields.lastElementChild.onclick=()=>{const target=[...root.querySelectorAll('.sw-reference')].find(el=>el.dataset.assetId===asset.id);target?.scrollIntoView({block:'nearest'});target?.focus({preventScroll:true});};
      top.append(fields); card.append(top);
      const description = element("details", "sw-asset-description");
      description.open = expandedDescriptions.has(asset.id);
      description.append(element("summary", "", "Saved description"));
      field(description, "Saved description", asset.description, (v) => mutate(() => asset.description = v), { area: true, rows: 4 });
      card.append(description);
      const analysis=element('div','sw-actions');analysis.append(button('Analyse image',()=>author('analyse',asset)),timingBadge('analyse',asset.analysis_attempt||asset.analysis_timing,asset.id));card.append(analysis);
      if(analysingAssetId===asset.id){
        const status=element('p','sw-help sw-analysis-status','Analysing image — waiting for the vision model…');status.setAttribute('role','status');card.append(status);
      }
      if(asset.analysis_error){
        const failure=element('p','sw-error',asset.analysis_error);failure.setAttribute('role','alert');card.append(failure);
        card.append(button('LLM connection',()=>{connection.open=true;connection.scrollIntoView({block:'nearest'});}));
      }
      if(asset.analysis_suggestion){
        const status=element('p','sw-help sw-analysis-status','Analysis ready — review below, then choose Use description.');status.setAttribute('role','status');card.append(status);
        field(card,'Analysis suggestion',asset.analysis_suggestion,v=>mutate(()=>asset.analysis_suggestion=v),{area:true,rows:3});
        card.append(button('Use description',()=>{description.open=true;mutate(()=>{asset.description=asset.analysis_suggestion;delete asset.analysis_suggestion;},true);}));
      }
      library.append(card);
    }
    libraryPanel.append(library);
    const promptPanel=element('section','sw-panel sw-prompt-panel');editor.append(promptPanel);
    const promptHeader = element("div", "sw-section-header"); promptHeader.append(element("h3", "", "H3 prompt"), button('Write prompt',()=>author('write'),'sw-primary')); promptPanel.append(promptHeader);
    promptPanel.append(element('p','sw-help','Write a structured prompt using this shot’s description and numbered pictures.'),timingBadge('write',latestTiming(current,'write')));
    operationError(promptPanel,current,'write');
    const status = element("p", "sw-status"); promptPanel.append(status);
    node._swRefreshStatus = () => {
      autoSelect.disabled=!!busy||!current.brief?.trim();
      const count = Math.max(5, Math.ceil(Number(current.duration_s) * 24)); const frames = count + ((5 - count) % 17 + 17) % 17;
      const stale = current.prompt_editor_dirty || (current.prompt_sections && !current.prompt_basis) || (current.prompt_basis && JSON.stringify(current.prompt_basis) !== JSON.stringify(basis(state, current)));
      const trimNote = current.continuity?.mode === "external_workflow" ? ", before external trim" : "";
      status.textContent = `${current.refs.length} references · ${frames} H3 input frames at 24 fps (${(frames / 24).toFixed(2)}s${trimNote}) · ${!current.prompt_sections ? "No prompt accepted" : stale ? "Prompt out of date — rewrite before generating" : current.prompt_origin==='llm'?'LLM prompt saved':'Manual prompt accepted'}`;
      referenceWarning.hidden=!current.prompt_sections||!stale;
      referenceWarning.textContent='Prompt out of date. Check the Picture numbers and rewrite or review the prompt before generating.';
      const run=root.querySelector('.sw-generate');if(run)run.disabled=!!busy||state.shots.some(s=>['queued','running'].includes(s.job?.status))||!current.prompt_sections||!!stale;
      const preview=root.querySelector('.sw-prompt-preview');
      if(preview){preview.dataset.stale=String(!!stale);preview.querySelector('.sw-prompt-preview-label').textContent=stale?'Saved prompt · Needs review':'Saved prompt';}
    };
    if(current.prompt_sections){
      const preview=element('div','sw-prompt-preview');preview.append(element('p','sw-prompt-preview-label','Saved prompt'));
      KEYS.forEach((key,index)=>{
        const section=element('section');section.append(element('h4','',SECTION_NAMES[index]));
        const text=element('p');
        for(const part of String(current.prompt_sections[key]||'').split(/(<Picture\s+\d+>)/g)){
          text.append(/^<Picture\s+\d+>$/.test(part)?element('mark','sw-picture-tag',part):document.createTextNode(part));
        }
        section.append(text);preview.append(section);
      });
      promptPanel.append(preview);
    }
    const details = element("details", "sw-prompt-editor"); details.open = promptExpanded ?? !!current.prompt_editor_dirty;
    details.append(element("summary", "", "Review / edit six-section prompt"));
    const defaultSections = Object.fromEntries(KEYS.map((key) => [key, ""]));
    field(details, "Prompt sections JSON", current.prompt_draft ?? JSON.stringify(current.prompt_sections || defaultSections, null, 2), (v) => mutate(() => { current.prompt_draft = v; current.prompt_editor_dirty = true; }), { area: true, rows: 8 });
    details.append(button("Accept manual prompt for this shot", () => {
      try {
        const sections = JSON.parse(current.prompt_draft ?? JSON.stringify(current.prompt_sections || defaultSections));
        if (Object.keys(sections).length !== 6 || KEYS.some((k) => typeof sections[k] !== "string" || !sections[k].trim())) throw Error("Fill all six sections with nonempty text. Use None for no music.");
        const text = KEYS.map((k) => sections[k]).join("\n");
        const indices = [...text.matchAll(/<Picture\s+(\d+)>/g)].map((m) => Number(m[1]));
        if (current.refs.some((r, i) => !indices.includes(i + 1)) || indices.some((i) => i < 1 || i > current.refs.length)) throw Error("Mention every selected <Picture N> and no unselected Picture tags.");
        if (/<(?:Audio|Video)\s+\d+>/.test(text)) throw Error("This prototype binds image references only.");
        current.prompt_sections = sections; current.prompt_basis = basis(state, current); current.prompt_editor_dirty = false;current.prompt_origin='manual'; error = ""; save(); render();
      } catch (cause) { error = cause.message; render(); }
    }, "sw-primary")); promptPanel.append(details);
    if(current.timings?.length){
      const table=element('table','sw-timings');const head=element('tr');
      for(const label of ['LLM stage','Model','Seconds','Calls'])head.append(element('th','',label));table.append(head);
      for(const timing of current.timings){const row=element('tr');for(const text of [timing.stage,timing.model||timing.calls?.[0]?.model||'—',Number.isFinite(timing.llm_ms)?(timing.llm_ms/1000).toFixed(2):'—',String(timing.calls?.length||0)])row.append(element('td','',text));table.append(row);}const history=element('details','sw-diagnostics');history.append(element('summary','','Call history'),table);promptPanel.append(history);
    }
    const output=element('section','sw-output');paintOutput(output,current);editor.append(output);
    if (error) editor.append(element("p", "sw-error", error));
    const connectionNotes=button('Workflow connection notes ↗',()=>{
      let note=node.graph._nodes.find(n=>n.properties?.shot_workspace_connection_notes);
      if(!note){
        note=LiteGraph.createNode('MarkdownNote')||LiteGraph.createNode('Note');
        if(!note?.widgets?.length){error='The built-in Note node is unavailable. Refresh ComfyUI and try again.';render();return;}
        const text=`## Connect your workflow

Start with the receiving workflow: find its prompt, reference images and continuation inputs. Keep its model, sampler and decoding chain in place.

**Prompt:** Workflow Interface · prompt → the workflow's text encoder.

**Reference images:** Workflow Interface · image_1 … image_9 → reference image inputs. Picture order matches Shot references.

**Video continuation:** Choose the previous decoded clip in native Load Video. Standard Media Outputs · video → Get Video Components → native Motion Context frames and audio.

**Latent continuation:** Choose the previous native cache in Motion Context Load Latent. Standard Media Outputs · context_latent → compatible native Motion Context input. LATENT types are not interchangeable across models.

For an independent shot, leave continuation disconnected. Advanced media ports creates the media passthrough node; Workflow interface creates or locates the authoring outputs. Connect only the inputs your workflow needs.`;
        note.title='Connect your workflow';note.properties.shot_workspace_connection_notes=true;
        note.widgets[0].value=text;note.widgets[0].callback?.(text);
        const anchor=node.graph._nodes.find(n=>n.type==='ShotWorkspaceInterface');
        note.pos=anchor?[anchor.pos[0]+anchor.size[0]+80,anchor.pos[1]]:[node.pos[0]+node.size[0]+720,node.pos[1]+140];
        note.setSize([480,320]);node.graph.add(note);
      }
      app.canvas.selectNode(note);app.canvas.centerOnNode(note);app.canvas.setDirty(true,true);
    });
    const footer = element("footer", "sw-footer"); footer.append(connectionNotes, extraMedia); root.append(footer);
    for(const section of editor.querySelectorAll('section'))section.tabIndex=-1;
    editor.scrollTop = previousScroll;
    libraryPanel.scrollTop = previousLibraryScroll;
    const updateNavigation=()=>{
      const threshold=sectionNav.getBoundingClientRect().bottom+32;
      let active=sections[0][1];
      for(const [,selector] of sections)if(editor.querySelector(selector).getBoundingClientRect().top<=threshold)active=selector;
      for(const item of sectionNav.children){if(item.dataset.section===active)item.setAttribute('aria-current','location');else item.removeAttribute('aria-current');}
    };
    editor.addEventListener('scroll',updateNavigation,{passive:true});scroll.addEventListener('scroll',updateNavigation,{passive:true});updateNavigation();
    if(pendingReferenceFocus){
      const target=[...root.querySelectorAll('.sw-reference')].find(row=>row.dataset.assetId===pendingReferenceFocus.assetId);
      const move=target?.querySelector(`[data-direction="${pendingReferenceFocus.direction}"]`);
      const focus=move&&!move.disabled?move:target||references;
      focus.focus({preventScroll:true});focus.scrollIntoView({block:'nearest'});pendingReferenceFocus=null;
    }
    node._swRefreshStatus();
    if(busy)root.querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=true);
  }
  for (const type of ["pointerdown", "mousedown", "dblclick", "keydown"]) root.addEventListener(type, (e) => e.stopPropagation());
  root.addEventListener("wheel", (e) => e.stopPropagation());
  const dom = node.addDOMWidget("shot_workspace_editor", "SHOT_WORKSPACE_EDITOR", root, { serialize: false });
  dom.computeSize = (width) => [width, Math.max(580, node.size[1] - 210)];
  node._swReload = () => { if (read()) {render();for(const s of state.shots)if(['queued','running'].includes(s.job?.status))startPoll(s.job.prompt_id,s.id);} };
  node._swApplyStoryboard=packet=>{state=applyStoryboard(state,packet);save();render();};
  node._swReload();
  return dom;
}

app.registerExtension({
  name: "ShotWorkspace.InterfacePrototype",
  async setup() {
    const css = document.createElement("link"); css.rel = "stylesheet"; css.href = new URL("./workspace.css", import.meta.url).href; document.head.append(css);
  },
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name === "ShotWorkspaceInterface") {
      const created = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () { created?.apply(this, arguments); this.setSize([300, 380]); };
    }
    if (nodeData.name === "ShotWorkspaceLLMRequest") {
      const executed = nodeType.prototype.onExecuted;
      nodeType.prototype.onExecuted = function (message) {
        executed?.apply(this, arguments);
        let view = this.widgets?.find((w) => w.name === "request_preview");
        if (!view) view = this.addWidget("text", "request_preview", "", () => {}, { multiline: true });
        view.value = message.text?.join("\n") || "";
      };
    }
    if (!['ShotWorkspace','ShotWorkspaceStoryboard'].includes(nodeData.name)) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      created?.apply(this, arguments);
      const storyboardMode=nodeData.name==='ShotWorkspaceStoryboard';
      const widget = this.widgets.find((w) => w.name === (storyboardMode?'storyboard_json':'workspace_json'));
      // Keep the actual backend widget serialized, with the editor as its view.
      widget.computeSize = () => [0, -4];
      if (widget.element) widget.element.style.display = "none";
      mount(this, widget,storyboardMode); this.setSize(storyboardMode?[760,1000]:[800, 940]);
    };
    const configured = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () { configured?.apply(this, arguments); this._swReload?.(); };
  },
});
