(() => {
"use strict";

const S={token:"",session:null,collections:[],runs:[],files:[],run:null};
const $=id=>document.getElementById(id);
const clear=n=>{while(n.firstChild)n.removeChild(n.firstChild)};
const el=(tag,value,cls)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=value==null?"Unknown / not established":String(value);if(cls)n.className=cls;return n};
const pre=v=>el("pre",JSON.stringify(v,null,2),"raw-json");
const text=v=>v==null?null:(typeof v==="object"?JSON.stringify(v):String(v));

function card(title,body,rows=[]){
  const a=el("article",undefined,"record-card");
  a.append(el("h3",title));
  for(const [k,v] of rows){
    if(v===undefined)continue;
    const p=el("p",undefined,"meta-row");
    p.append(el("strong",`${k}: `),document.createTextNode(v==null?"Unknown / not established":String(v)));
    a.append(p);
  }
  if(body instanceof Node)a.append(body);else if(body!=null)a.append(el("p",body));
  return a;
}
function toast(msg,kind="info"){const n=$("toast");n.textContent=msg;n.dataset.kind=kind;n.hidden=false;clearTimeout(toast.t);toast.t=setTimeout(()=>n.hidden=true,4500)}
async function api(path,opt={}){const h={Accept:"application/json"};if(S.token)h["X-QSOL-Control-Token"]=S.token;const init={method:opt.method||"GET",headers:h};if(opt.body!==undefined){h["Content-Type"]="application/json";init.body=JSON.stringify(opt.body)}const r=await fetch(path,init),p=await r.json().catch(()=>({error:`HTTP ${r.status}`}));if(!r.ok)throw new Error(p.error||`HTTP ${r.status}`);return p}
function activate(name,focus=false){for(const t of document.querySelectorAll('[role="tab"]')){const yes=t.dataset.panel===name;t.setAttribute("aria-selected",String(yes));t.tabIndex=yes?0:-1;if(yes&&focus)t.focus()}for(const p of document.querySelectorAll('[role="tabpanel"]'))p.hidden=p.dataset.view!==name}
function tabs(){const ts=[...document.querySelectorAll('[role="tab"]')];ts.forEach((t,i)=>{t.onclick=()=>activate(t.dataset.panel);t.onkeydown=e=>{if(!["ArrowLeft","ArrowRight","Home","End"].includes(e.key))return;e.preventDefault();const j=e.key==="Home"?0:e.key==="End"?ts.length-1:e.key==="ArrowLeft"?(i-1+ts.length)%ts.length:(i+1)%ts.length;activate(ts[j].dataset.panel,true)}})}
const pLabel=k=>({unknown:S.session?.model_state_labels?.unknown||"Unknown / not established",locally_verified:S.session?.model_state_labels?.locally_verified||"Locally verified",provider_reported:S.session?.model_state_labels?.provider_reported||"Provider reported",inferred:S.session?.model_state_labels?.inferred||"Inferred — not verified",observed:S.session?.model_state_labels?.observed||"Observed"}[k]||String(k||"unknown"));
function options(select,rows,blank){const old=select.value;clear(select);if(blank){const o=el("option",blank);o.value="";select.append(o)}for(const [value,label] of rows){const o=el("option",label);o.value=value;select.append(o)}if([...select.options].some(o=>o.value===old))select.value=old}
async function refreshCollections(){const p=await api("/api/collections");S.collections=p.collections||[];const rows=S.collections.map(c=>[c.collection_id,`${c.name} · ${c.head_snapshot_id.slice(0,18)}…`]);options($("ask-collection"),rows,"No Collection");options($("collection-browser"),rows,"Select Collection");if($("collection-browser").value)await showCollection($("collection-browser").value)}
async function refreshRuns(){const p=await api("/api/runs");S.runs=p.runs||[];const rows=S.runs.map(r=>[r.run_id,`${r.created_at} · ${r.mode} · ${r.question.slice(0,64)}`]);options($("run-picker"),rows,"Select a run…");options($("compare-left"),rows,"Original run");options($("compare-right"),rows,"Comparison run")}
async function b64(file){const a=new Uint8Array(await file.arrayBuffer());let s="";for(let i=0;i<a.length;i+=32768)s+=String.fromCharCode(...a.subarray(i,i+32768));return btoa(s)}
async function upload(){S.files=[];clear($("attached-files"));for(const f of [...$("file-input").files]){if(f.size>S.session.max_upload_bytes)throw new Error(`${f.name} exceeds upload limit`);const p=await api("/api/files",{method:"POST",body:{filename:f.name,media_type:f.type||"application/octet-stream",privacy_class:"INTERNAL",retention_class:"SESSION",content_base64:await b64(f)}});S.files.push(p.file.file_id);$("attached-files").append(el("span",`${f.name} · ${p.file.file_id.slice(0,18)}…`,"file-token"))}}
const lines=id=>[...new Set($(id).value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean))];

async function ask(e){
  e.preventDefault();$("composer-status").textContent="Working";
  try{
    await upload();
    const mode=document.querySelector('input[name="mode"]:checked').value;
    const body={question:$("question").value,mode,file_ids:S.files,collection_id:$("ask-collection").value||null,nexus_mode:$("nexus-mode").value||"analytical",nexus_evidence_refs:lines("nexus-evidence-refs")};
    const m=$("members-json").value.trim();if(m)body.members=JSON.parse(m);
    const p=await api("/api/ask",{method:"POST",body});
    await loadRun(p.run_id,p);await refreshRuns();$("composer-status").textContent="Recorded";activate(mode==="council"?"council":"evidence");toast("Immutable run recorded","success");
  }catch(err){$("composer-status").textContent="Failed";toast(err.message,"error")}
}

function latestEvidence(v){return (v.evidence_events||[]).at(-1)?.payload||{availability:"unknown",state:"unknown",evidence_refs:[]}}
function latestCouncil(v){const payloads=(v.response_events||[]).map(e=>e.payload).reverse();return payloads.find(p=>p?.protocol==="qsol-control-nexus-council-response/1"||p?.protocol==="qsol-control-webui-council-status/1")||null}
async function loadRun(id,askResult=null){if(!id)return;const v=askResult?.run_view||await api(`/api/runs/${encodeURIComponent(id)}`);S.run=v;renderEvidence(askResult?.oracle||latestEvidence(v));renderCouncil(askResult?.council||latestCouncil(v));renderSources(v);renderTimeline(v);renderReceipts(v);renderModels(v.model_states||[]);renderLattice(v.lattice);$("run-picker").value=id}

function renderEvidence(p){
  const root=$("evidence-view");clear(root);const st=p?.state||"unknown";$("evidence-status").textContent=st.toUpperCase();
  root.append(card(`ORACLE: ${st}`,null,[["Availability",p?.availability],["Authority",p?.authority]]));
  if(p?.freshness&&typeof p.freshness==="object"){
    const f=p.freshness;
    root.append(card("Freshness",null,[["State",f.state],["Source time",f.source_time],["Evaluated at",f.evaluated_at],["Age seconds",f.age_seconds],["Maximum age seconds",f.max_age_seconds],["Fresh means true",f.fresh_means_true],["Stale means false",f.stale_means_false]]));
  }else{
    root.append(card("Freshness","Unknown / not established"));
  }
  for(const r of p?.evidence_refs||[])root.append(card("Observation",null,[["Event",r.event_id||r.event_hash],["Observed",r.observed_at],["Source",text(r.source)],["Provenance",r.provenance_kind],["Evidence state",r.evidence_state]]));
  for(const m of p?.missing_evidence||[])root.append(card("Missing evidence",m));
  for(const q of p?.suggested_searches||[])root.append(card("Suggested search · NOT EVIDENCE",q));
}

function renderCouncil(p){
  const root=$("council-view"),minor=$("minority-view");clear(root);clear(minor);
  if(!p){root.append(card("No Council result","NEXUS was not invoked."));minor.append(card("No minority reports","No Council result selected."));return}
  root.append(card("Council result",p.error||null,[["Availability",p.availability],["Session",p.session_ref],["Receipt",p.receipt_ref],["Disposition",p.consensus?.disposition],["Outcome",p.consensus?.consensus_outcome],["Threshold",p.consensus?.consensus_threshold?`${p.consensus.consensus_threshold.numerator}/${p.consensus.consensus_threshold.denominator}`:null],["Threshold met",p.consensus?.threshold_met],["Label",p.consensus?.consensus_label],["Authority",p.authority]]));
  if(Array.isArray(p.roster)){
    root.append(card("Canonical Council roster","NEXUS committed seat order. Vote weights and epistemic privileges are rendered as recorded."));
    p.roster.forEach((seat,index)=>root.append(card(`Seat ${index+1}: ${seat.member_id||"Unknown"}`,null,[["Model",seat.model_id],["Adapter",seat.adapter_id],["Vote weight",seat.vote_weight],["Epistemic privilege",seat.epistemic_privilege]])));
  }
  for(const ph of p.phases||[]){const c=card(`Phase ${ph.phase}`,null);c.append(pre(ph.submissions));root.append(c)}
  if(p.sealed_ballot)root.append(card("SEALED BALLOT",pre(p.sealed_ballot),[["Commitments verified",p.sealed_ballot.commitments_verified]]));
  for(const r of p.minority_reports||[])minor.append(card(r.member_id||"Minority",r.rationale,[["Choice",r.choice]]));
  if(!minor.children.length)minor.append(card("No minority reports","No preserved minority report in this result."));
}

function renderSources(v){
  const root=$("sources-view");clear(root);
  if(v.collection_snapshot)root.append(card("Exact Collection snapshot used by run",null,[["Collection",v.collection?.collection_id],["Snapshot",v.collection_snapshot.snapshot_id],["Revision",v.collection_snapshot.revision],["Current HEAD",v.collection?.head_snapshot_id],["Historical snapshot",v.collection?.head_snapshot_id!==v.collection_snapshot.snapshot_id]]));
  for(const s of v.sources||[]){
    const rows=[["Ref",s.ref]];
    if(s.source!==undefined)rows.push(["Source",text(s.source)]);
    if(s.privacy_class!==undefined)rows.push(["Privacy",s.privacy_class]);
    if(s.observed_at!==undefined)rows.push(["Observed",s.observed_at]);
    if(s.provenance_kind!==undefined)rows.push(["Provenance",s.provenance_kind]);
    rows.push(["Authority",s.authority]);
    root.append(card(s.kind,s.filename||s.ref,rows));
  }
  if(!root.children.length)root.append(card("No sources","No source references attached to this run."));
}

function renderTimeline(v){
  const root=$("timeline-view");clear(root);
  for(const e of v.events||[]){
    root.append(card(`${e.sequence}. CONTROL ${e.kind}`,null,[["Recorded at",e.occurred_at],["Event",e.event_id],["Address",e.lattice_address]]));
    if(e.kind==="evidence"&&Array.isArray(e.payload?.evidence_refs)){
      for(const r of e.payload.evidence_refs){
        root.append(card("ORACLE observation",null,[["Observed at",r.observed_at],["ORACLE event",r.event_id||r.event_hash],["Source",text(r.source)],["Provenance",r.provenance_kind],["CONTROL recorded at",e.occurred_at]]));
      }
    }
  }
  if(!root.children.length)root.append(card("No events","Empty run event chain."));
}

function renderReceipts(v){
  const root=$("receipts-view");clear(root);
  for(const e of v.receipt_events||[])root.append(card("CONTROL receipt event",pre(e.payload),[["Event",e.event_id]]));
  const council=latestCouncil(v);
  if(council?.receipt_verification)root.append(card("NEXUS receipt verification",pre(council.receipt_verification),[["Receipt",council.receipt_ref],["Session",council.session_ref]]));
  if(council?.epoch_admission_verification)root.append(card("NEXUS epoch admission verification",pre(council.epoch_admission_verification),[["Epoch receipt",council.epoch_admission_receipt_ref]]));
  if(!root.children.length)root.append(card("No receipts","No receipt or verification material recorded."));
}

function renderModels(states){const root=$("models-view");clear(root);for(const s of states){const c=card(`${s.model.provider} / ${s.model.model_id}`,null,[["Runtime",`${s.model.runtime} ${s.model.runtime_version||""}`],["Revision",s.model.revision],["Quantization",s.model.quantization],["Boundary",s.epistemic_boundary]]);const table=document.createElement("dl");for(const [path,kind] of Object.entries(s.field_provenance||{})){table.append(el("dt",path),el("dd",pLabel(kind),`provenance ${kind}`))}c.append(el("h4",S.session.model_state_labels.provenance_heading),table,pre(s));root.append(c)}if(!states.length)root.append(card("No model-state records","Unknown / not established"))}
function renderLattice(p){const root=$("lattice-view");clear(root);for(const c of p?.cells||[]){const b=document.createElement("button");b.type="button";b.className="lattice-cell";b.textContent=`${c.address}\n${c.count} records`;b.title="Logical storage address. GEOMETRY ≠ TRUTH.";b.onclick=()=>{const d=document.createElement("dialog");d.append(el("h3",c.address),el("p","Logical navigation only. GEOMETRY ≠ TRUTH."),pre(c.records));const x=el("button","Close");x.onclick=()=>d.close();d.append(x);document.body.append(d);d.onclose=()=>d.remove();d.showModal()};root.append(b)}}

async function showCollection(id){if(!id)return;try{const p=await api(`/api/collections/${encodeURIComponent(id)}`),root=$("collection-detail");clear(root);root.append(card(p.collection.name,null,[["Collection",p.collection.collection_id],["HEAD",p.collection.head_snapshot_id],["Snapshot",p.snapshot.snapshot_id],["Revision",p.snapshot.revision]]));for(const f of p.files||[])root.append(card(f.filename,f.file_id,[["Privacy",f.privacy_class]]))}catch(e){toast(e.message,"error")}}
async function createCollection(e){e.preventDefault();try{const p=await api("/api/collections",{method:"POST",body:{name:$("collection-name").value,privacy_class:"INTERNAL",retention_class:"ARCHIVE"}});$("collection-name").value="";await refreshCollections();$("collection-browser").value=p.collection_id;await showCollection(p.collection_id);toast("Collection created","success")}catch(e){toast(e.message,"error")}}
async function updateCollection(){const id=$("collection-browser").value;if(!id)return toast("Choose a Collection","error");try{const d=await api(`/api/collections/${encodeURIComponent(id)}`);await api(`/api/collections/${encodeURIComponent(id)}/members`,{method:"POST",body:{add:lines("collection-add-files"),remove:lines("collection-remove-files"),expected_head_snapshot_id:d.snapshot.snapshot_id}});$("collection-add-files").value=$("collection-remove-files").value="";await refreshCollections();$("collection-browser").value=id;await showCollection(id);toast("Immutable membership snapshot created","success")}catch(e){toast(e.message,"error")}}
async function searchCollection(){const id=$("collection-browser").value,q=$("collection-search").value.trim();if(!id||!q)return;try{const p=await api(`/api/search?collection_id=${encodeURIComponent(id)}&q=${encodeURIComponent(q)}&limit=20`),root=$("collection-search-results");clear(root);root.append(card("Exact snapshot searched",p.snapshot_id,[["Meaning",p.score_meaning]]));for(const r of p.results||[])root.append(card(`${r.rank}. ${r.file.filename}`,null,[["Similarity",r.score],["File",r.file_id],["Snapshot",r.snapshot_id],["Meaning",r.score_meaning]]))}catch(e){toast(e.message,"error")}}

async function dna(full){
  try{
    const body={file_id:$("dna-file-id").value.trim(),traversal_id:$("dna-traversal").value};
    if(full){body.allow_restricted=body.acknowledge_reversible_sensitive_export=$("dna-restricted-ack").checked;const actor=$("dna-actor").value.trim();if(actor)body.actor=actor}
    const p=await api(full?"/api/dna/export":"/api/dna/inspect",{method:"POST",body}),root=$("dna-view");clear(root);
    if(full){const blob=new Blob([JSON.stringify(p,null,2)],{type:"application/json"}),a=el("a","Download deterministic projection JSON","download-link");a.href=URL.createObjectURL(blob);a.download=`${p.projection_id.replace(":","-")}.json`;root.append(card("Projection ready","Reversible recovery data, not biological evidence."),a)}else root.append(card("Derived reversible projection",pre(p),[["Projection",p.projection_id],["Traversal",p.traversal_id],["Authority",p.authority]]));
  }catch(e){toast(e.message,"error")}
}

async function compare(){const l=$("compare-left").value,r=$("compare-right").value;if(!l||!r)return;try{const p=await api(`/api/replay-compare?left_run_id=${encodeURIComponent(l)}&right_run_id=${encodeURIComponent(r)}`),root=$("compare-view");clear(root);root.append(card("Run comparison",pre(p.changed_run_fields),[["Left NEXUS refs",text(p.left_nexus_refs)],["Right NEXUS refs",text(p.right_nexus_refs)],["Replay execution",p.comparison_is_replay_execution],["Phase 7 replay implemented",p.phase7_replay_execution_implemented],["Authority",p.authority]]),card("Model-state comparison · NOT MIND COMPARISON",pre(p.model_state_comparison)))}catch(e){toast(e.message,"error")}}

function renderReplayReport(report,root){
  clear(root);
  root.append(card("Replay comparison report",null,[["Report",report.report_id],["Classification",report.classification],["Original immutable",report.original_result?.immutable],["Authority",report.authority]]));
  root.append(card("Evidence changes",pre(report.evidence),[["Current evidence is original evidence",report.evidence?.current_evidence_is_original_evidence]]));
  root.append(card("Collection membership drift",pre(report.collection),[["Replay bound to original snapshot",report.collection?.replay_bound_to_original_snapshot]]));
  root.append(card("Retrieval / index basis",pre(report.retrieval_index),[["Legacy original basis incomplete",report.retrieval_index?.legacy_original_basis_incomplete]]));
  root.append(card("Council roster + runtime",pre(report.council),[["Consensus is truth",report.council?.consensus_is_truth]]));
  root.append(card("Model revision / runtime metadata · NOT MIND COMPARISON",pre(report.model_state)));
  root.append(card("Request configuration changes",pre(report.configuration)));
}

async function classifyReplay(){
  const id=$("compare-left").value;if(!id)return toast("Choose an original run","error");
  try{
    const p=await api(`/api/replay/classify?run_id=${encodeURIComponent(id)}`),root=$("replay-classification-view");clear(root);
    root.append(card(`Replay class: ${p.classification}`,null,[["Executable",p.can_execute],["Original replayability",p.original_replayability],["Basis",p.basis_status],["Index status",p.retrieval_index_status],["Original Collection snapshot",p.original_collection_snapshot_id],["Current Collection HEAD",p.current_collection_head_snapshot_id],["Collection drift",p.collection_membership_drift],["Council roster changed",p.council_roster_changed],["Exact replay claimed",p.exact_replay_claimed],["Authority",p.authority]]),pre(p));
  }catch(e){toast(e.message,"error")}
}

async function executeReplay(){
  const id=$("compare-left").value;if(!id)return toast("Choose an original run","error");
  try{
    const p=await api("/api/replay",{method:"POST",body:{run_id:id,allow_changed_configuration:$("replay-allow-changed-config").checked}}),root=$("replay-execution-view");
    renderReplayReport(p.report,root);
    root.prepend(card("Replay execution",null,[["Replay",p.replay.replay_id],["Replay run",p.replay.replay_run_id],["Class",p.replay.classification],["Original immutable",p.original_result_immutable],["Exact replay claimed",p.replay.exact_replay_claimed]]));
    await refreshRuns();$("compare-left").value=id;$("compare-right").value=p.replay.replay_run_id;toast("Classified replay recorded without rewriting original","success");
  }catch(e){toast(e.message,"error")}
}

async function researchTimeline(){
  const id=$("compare-left").value;if(!id)return toast("Choose an original run","error");
  try{
    const p=await api(`/api/research-timeline?run_id=${encodeURIComponent(id)}&limit=100`),root=$("research-timeline-view");clear(root);
    root.append(card("Recurring-question timeline",p.question,[["Timeline",p.timeline_id],["Matching runs",p.total_matching_runs],["Returned",p.returned_runs],["Truncated",p.truncated],["Authority",p.authority]]));
    for(const row of p.runs||[])root.append(card(`${row.created_at} · ${row.mode}`,row.run_id,[["Evidence",row.evidence_state],["Collection",text(row.collection_ref)],["Council disposition",row.council_disposition],["NEXUS runtime",row.nexus_runtime_version],["Replay of",row.replay_of]]));
    if((p.transitions||[]).length)root.append(card("Longitudinal transitions",pre(p.transitions),[["Timeline is truth",p.timeline_is_truth]]));
  }catch(e){toast(e.message,"error")}
}

async function health(){
  const root=$("health-view"),timelock=$("timelock-view");clear(root);clear(timelock);
  try{
    const h=await api("/api/health");
    for(const [k,v] of Object.entries(h.services||{}))root.append(card(k,v.error||null,[["Configured",v.configured],["Available",v.available]]));
  }catch(e){root.append(card("Health unavailable",e.message));toast(e.message,"error")}
  try{
    const t=await api("/api/oracle/timelock");timelock.append(pre(t));
  }catch(e){timelock.append(card("Timelock unavailable",e.message,[["ELIGIBLE != EXECUTED",true]]))}
}

async function boot(){
  tabs();
  try{S.session=await api("/api/session");S.token=S.session.session_token;$("model-panel-title").textContent=S.session.model_state_labels.panel_title;$("model-boundary").textContent=S.session.model_state_labels.boundary_badge;$("question").maxLength=S.session.max_question_characters||2048;await Promise.all([refreshCollections(),refreshRuns(),health()]);renderLattice(await api("/api/lattice"))}catch(e){toast(`Bootstrap failed: ${e.message}`,"error")}
  $("ask-form").onsubmit=ask;$("run-picker").onchange=e=>loadRun(e.target.value).catch(x=>toast(x.message,"error"));$("collection-create").onsubmit=createCollection;$("collection-browser").onchange=e=>showCollection(e.target.value);$("collection-update-button").onclick=updateCollection;$("collection-search-button").onclick=searchCollection;$("dna-inspect").onclick=()=>dna(false);$("dna-export").onclick=()=>dna(true);$("compare-runs").onclick=compare;$("replay-classify").onclick=classifyReplay;$("replay-execute").onclick=executeReplay;$("research-timeline").onclick=researchTimeline;$("refresh-health").onclick=health;for(const r of document.querySelectorAll('input[name="mode"]'))r.onchange=()=>$("council-options").open=document.querySelector('input[name="mode"]:checked').value==="council";
}

document.addEventListener("DOMContentLoaded",boot);
})();
