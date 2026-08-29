import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity, AlertCircle, ArrowLeft, ArrowRight, CalendarDays, Check,
  CheckCircle2, ChevronDown, CircleUserRound, ClipboardCheck, Clock3,
  FileImage, FilePlus2, FileText, HeartPulse, History, LayoutDashboard,
  Menu, MessageSquareText, MoreHorizontal, Pill, Plus, Search, ShieldCheck,
  Sparkles, Stethoscope, UploadCloud, Users, X, XCircle
} from 'lucide-react';
import './styles.css';
import { api } from './api';

const recordsSeed = [
  { id: 1, name: 'Cardiology consultation', date: '12 Aug 2026', type: 'Consultation', status: 'analysed', icon: FileText, tone: 'blue' },
  { id: 2, name: 'Complete blood count', date: '09 Aug 2026', type: 'Lab report', status: 'analysed', icon: FileText, tone: 'violet' },
  { id: 3, name: 'Medicine strip — Metformin', date: 'Uploaded today', type: 'Medicine photo', status: 'review', icon: FileImage, tone: 'orange' },
  { id: 4, name: 'Chest X-ray', date: '18 May 2026', type: 'Imaging', status: 'analysed', icon: FileImage, tone: 'cyan' },
];

const timeline = [
  { date: 'Today', title: 'Pre-visit intake completed', body: 'Reports increased fatigue and ankle swelling over the last 3 weeks.', tag: 'Patient reported', tone: 'green' },
  { date: '12 Aug 2026', title: 'Cardiology consultation', body: 'Hypertension noted as suboptimally controlled. Amlodipine increased to 10 mg.', tag: 'Consultation', tone: 'blue' },
  { date: '09 Aug 2026', title: 'Laboratory panel', body: 'HbA1c 8.1% ↑ · eGFR 62 mL/min · Hb 11.2 g/dL ↓', tag: 'Lab report', tone: 'violet' },
  { date: '18 May 2026', title: 'Chest X-ray', body: 'Mild cardiomegaly. No focal consolidation or pleural effusion.', tag: 'Imaging', tone: 'cyan' },
  { date: '04 Feb 2024', title: 'Type 2 diabetes diagnosed', body: 'Metformin 500 mg twice daily initiated.', tag: 'Historical record', tone: 'gray' },
];

function App() {
  const [view, setView] = useState('doctor');
  const [activeNav, setActiveNav] = useState('Patients');
  const [tab, setTab] = useState('Overview');
  const [search, setSearch] = useState('');
  const [records, setRecords] = useState(recordsSeed);
  const [toast, setToast] = useState('');
  const [mobileNav, setMobileNav] = useState(false);
  const [apiStatus, setApiStatus] = useState('connecting');
  const [patientId, setPatientId] = useState(localStorage.getItem('docpilot_patient_id') || '');
  const fileRef = useRef(null);

  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600); };
  useEffect(() => {
    let active = true;
    async function connect() {
      try {
        await api.health();
        let id = localStorage.getItem('docpilot_patient_id');
        if (id) {
          try { await api.getPatient(id); } catch { id = null; }
        }
        if (!id) {
          const patient = await api.createPatient({ full_name: 'Arun Kumar', date_of_birth: '1968-03-14', sex: 'male', phone: '+91 98765 43210', blood_group: 'B+' });
          id = patient.id;
          localStorage.setItem('docpilot_patient_id', id);
        }
        const remote = await api.records(id);
        if (!active) return;
        setPatientId(id);
        if (remote.length) setRecords(remote.map(toUiRecord));
        setApiStatus('connected');
      } catch (error) {
        if (active) { setApiStatus('offline'); notify(`Backend unavailable: ${error.message}`); }
      }
    }
    connect();
    return () => { active = false; };
  }, []);

  const addFiles = async (files) => {
    const additions = [...files].map((f, i) => ({ id: Date.now() + i, name: f.name, date: 'Uploaded just now', type: f.type.startsWith('image') ? 'Medicine / record photo' : 'Medical document', status: 'review', icon: f.type.startsWith('image') ? FileImage : FileText, tone: 'orange' }));
    setRecords((r) => [...additions, ...r]);
    if (!patientId) { notify('Backend is not connected; showing files locally'); return; }
    try {
      await Promise.all([...files].map(file => api.uploadRecord(patientId, file)));
      const remote = await api.records(patientId);
      setRecords(remote.map(toUiRecord));
      notify(`${additions.length} record${additions.length === 1 ? '' : 's'} uploaded and queued for processing`);
    } catch (error) {
      notify(`Upload failed: ${error.message}`);
    }
  };

  const filtered = useMemo(() => records.filter(r => r.name.toLowerCase().includes(search.toLowerCase())), [records, search]);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
        <div className="brand"><div className="brand-mark"><HeartPulse size={21}/></div><span>DocPilot</span></div>
        <button className="close-mobile" onClick={() => setMobileNav(false)}><X size={20}/></button>
        <nav>
          <p className="nav-label">Workspace</p>
          {[
            ['Overview', LayoutDashboard], ['Patients', Users], ['Appointments', CalendarDays], ['Messages', MessageSquareText]
          ].map(([label, Icon]) => <button key={label} className={activeNav === label ? 'active' : ''} onClick={() => { setActiveNav(label); setMobileNav(false); if(label !== 'Patients') notify(`${label} workspace is ready for integration`); }}><Icon size={18}/><span>{label}</span>{label === 'Messages' && <b className="count">3</b>}</button>)}
          <p className="nav-label second">Clinical tools</p>
          {[['Record analyser', Sparkles], ['All records', FileText], ['Audit trail', History]].map(([label, Icon]) => <button key={label} onClick={() => notify(`${label} opened in demo mode`)}><Icon size={18}/><span>{label}</span></button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy"><ShieldCheck size={18}/><div><strong>Private & encrypted</strong><small>Clinical data protected</small></div></div>
          <button className="profile"><AvatarImage className="avatar" src="/assets/avatars/doctor-rhea.png" initials="DR" alt="Dr. Rhea Menon"/><span><strong>Dr. Rhea Menon</strong><small>Internal Medicine</small></span><MoreHorizontal size={18}/></button>
        </div>
      </aside>
      {mobileNav && <div className="scrim" onClick={() => setMobileNav(false)}/>}

      <main>
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setMobileNav(true)}><Menu size={21}/></button>
          <div className="breadcrumbs"><button>{view === 'doctor' ? 'Patients' : 'My health'}</button><span>/</span><strong>{view === 'doctor' ? 'Arun Kumar' : 'My profile'}</strong></div>
          <div className="top-actions">
            <span className={`api-status ${apiStatus}`}><i/>{apiStatus === 'connected' ? 'API connected' : apiStatus === 'offline' ? 'API offline' : 'Connecting'}</span>
            <div className="mode-switch"><button className={view === 'patient' ? 'selected' : ''} onClick={() => setView('patient')}>Patient view</button><button className={view === 'doctor' ? 'selected' : ''} onClick={() => setView('doctor')}>Doctor view</button></div>
            <button className={`mini-avatar profile-trigger ${view}`} title={view === 'doctor' ? 'Doctor profile' : 'Patient profile'} aria-label={view === 'doctor' ? 'Open doctor profile' : 'Open patient profile'} onClick={() => notify(view === 'doctor' ? 'Doctor profile opened' : 'Patient profile opened')}><AvatarImage src={view === 'doctor' ? '/assets/avatars/doctor-rhea.png' : '/assets/avatars/patient-arun.png'} initials={view === 'doctor' ? 'DR' : 'AK'} alt=""/></button>
          </div>
        </header>

        {view === 'doctor' ? (
          <DoctorView tab={tab} setTab={setTab} search={search} setSearch={setSearch} records={filtered} notify={notify} onUpload={() => fileRef.current?.click()} />
        ) : (
          <PatientView records={records} onUpload={() => fileRef.current?.click()} notify={notify}/>
        )}
        <input ref={fileRef} type="file" hidden multiple accept="image/*,.pdf,.doc,.docx" onChange={(e) => addFiles(e.target.files)} />
      </main>
      {toast && <div className="toast"><CheckCircle2 size={18}/>{toast}</div>}
    </div>
  );
}

function DoctorView({tab, setTab, search, setSearch, records, notify, onUpload}) {
  return <div className="page">
    <div className="doctor-sticky-context">
      <section className="patient-head">
        <button className="back"><ArrowLeft size={18}/></button>
        <div className="patient-avatar"><AvatarImage src="/assets/avatars/patient-arun.png" initials="AK" alt="Arun Kumar"/></div>
        <div className="patient-title"><div><h1>Arun Kumar</h1><span className="status-pill"><span/> Ready for review</span></div><p>58 years · Male · Patient ID DP-2048 · Blood group B+</p></div>
        <div className="head-actions"><button className="btn secondary" onClick={onUpload}><UploadCloud size={17}/> Add records</button><button className="btn primary" onClick={() => notify('Consultation note started')}><Stethoscope size={17}/> Start consultation</button></div>
      </section>

      <div className="warning-strip"><AlertCircle size={18}/><div><strong>2 important record gaps identified</strong><span>Latest ECG and renal function follow-up are not available.</span></div><button onClick={() => setTab('Record gaps')}>Review gaps <ArrowRight size={15}/></button></div>

      <div className="tabs">{['Overview','Timeline','All records','Record gaps'].map(t => <button key={t} className={tab===t?'active':''} onClick={() => setTab(t)}>{t}{t==='Record gaps'&&<b>2</b>}</button>)}</div>
    </div>

    {tab === 'Overview' && <Overview notify={notify}/>} 
    {tab === 'Timeline' && <Timeline/>}
    {tab === 'All records' && <Records records={records} search={search} setSearch={setSearch} onUpload={onUpload}/>} 
    {tab === 'Record gaps' && <Gaps notify={notify}/>} 
  </div>
}

function Overview({notify}) { const [detail, setDetail] = useState(null); return <div className="doctor-cockpit">
  <section className="visit-hero card">
    <div className="visit-meta"><div className="visit-label"><MessageSquareText size={17}/> REASON FOR VISIT</div><button onClick={() => notify('9 verified and 3 patient-provided sources')}><ShieldCheck size={15}/> Based on 12 records</button></div>
    <div className="visit-headline status-worsening"><h3>Progressive fatigue with swelling in both ankles</h3><span><Activity size={15}/> Worsening</span></div>
    <div className="symptom-facts"><span><Clock3 size={16}/><strong>Symptoms for 3 weeks</strong></span><span><Activity size={16}/><strong>Gradually worsening</strong></span><span><CalendarDays size={16}/><strong>Worse in the evening</strong></span></div>
    <blockquote className="patient-quote"><p>“I feel unusually tired and my shoes become tight by evening.”</p><cite>— Patient reported today</cite></blockquote>
    <div className="clinical-ribbon">
      <div className="ribbon-danger"><AlertCircle size={19}/><span><small>ALLERGY</small><strong>Penicillin</strong></span></div>
      <div><HeartPulse size={19}/><span><small>BLOOD PRESSURE</small><strong>154/94 <em>High</em></strong></span></div>
      <div><Activity size={19}/><span><small>RECENT HbA1c</small><strong>8.1% <em>High</em></strong></span></div>
      <div><Clock3 size={19}/><span><small>LAST CONSULT</small><strong>12 Aug 2026</strong></span></div>
    </div>
  </section>

  <div className="doctor-layout">
    <div className="doctor-main">
      <section className="card focus-card">
        <div className="readable-title priority-heading"><span className="title-icon amber"><AlertCircle size={20}/></span><div><h3>Review today</h3></div><b>3</b></div>
        <div className="priority-row critical"><span className="priority-type">DOSE CONFLICT</span><div><h4>Amlodipine: <strong>10 mg</strong> in note vs <strong>5 mg</strong> on strip</h4><button className="evidence-link" onClick={() => setDetail('dose')}><FileText size={14}/> See evidence</button></div><button onClick={() => notify('Medication reconciliation opened')}>Verify dose <ArrowRight size={16}/></button></div>
        <div className="priority-row symptom"><span className="priority-type">NEW SYMPTOM</span><div><h4>Fatigue + swelling in both ankles · <strong>3 weeks</strong></h4><button className="evidence-link" onClick={() => setDetail('symptom')}>Why this matters</button></div><button onClick={() => notify('Assessment checklist opened')}>Examine <ArrowRight size={16}/></button></div>
        <div className="priority-row missing"><span className="priority-type">MISSING RESULT</span><div><h4>Repeat renal function test is overdue</h4><button className="evidence-link" onClick={() => setDetail('renal')}>See previous plan</button></div><button onClick={() => notify('Record request prepared')}>Request test <ArrowRight size={16}/></button></div>
      </section>

      <details className="card doctor-disclosure story-card">
        <summary><div className="readable-title"><span className="title-icon green"><History size={20}/></span><div><h3>Changes since 12 Aug 2026</h3><p>Symptoms, medicines and investigation results</p></div><ChevronDown size={20}/></div></summary>
        <div className="change-grid">
          <div><span className="change-date">Today</span><h4>Fatigue and ankle swelling reported</h4><p>Progressive over 3 weeks; no previous similar symptom found.</p></div>
          <div><span className="change-date">12 Aug</span><h4>Amlodipine increased</h4><p>5 mg → 10 mg daily due to suboptimal BP control.</p></div>
          <div><span className="change-date">09 Aug</span><h4>Diabetes and anaemia need review</h4><p>HbA1c 8.1% · Haemoglobin 11.2 g/dL · eGFR 62.</p></div>
        </div>
      </details>

      <div className="doctor-two-col">
        <details className="card readable-list doctor-disclosure"><summary><div className="readable-title"><span className="title-icon green"><Activity size={20}/></span><div><h3>4 active problems</h3><p>2 require review today</p></div><ChevronDown size={20}/></div></summary><div className="disclosure-body">
          <Condition name="Type 2 diabetes mellitus" meta="HbA1c 8.1% · Above target" tag="Review" tone="red"/>
          <Condition name="Essential hypertension" meta="Latest BP 154/94 mmHg" tag="Uncontrolled" tone="orange"/>
          <Condition name="Mild anaemia" meta="Hb 11.2 g/dL · New finding" tag="Investigate" tone="violet"/>
          <Condition name="Dyslipidaemia" meta="Stable on atorvastatin" tag="Stable" tone="green"/>
        </div></details>
        <details className="card readable-list doctor-disclosure"><summary><div className="readable-title"><span className="title-icon green"><Pill size={20}/></span><div><h3>5 current medicines</h3><p>2 need confirmation</p></div><ChevronDown size={20}/></div></summary><div className="disclosure-body">
          <Medicine name="Metformin" dose="500 mg · Twice daily" verified/>
          <Medicine name="Amlodipine" dose="Dose conflict · Verify today" />
          <Medicine name="Atorvastatin" dose="20 mg · At night" verified/>
          <Medicine name="Telmisartan" dose="40 mg · Frequency unclear" />
          <button className="panel-link" onClick={() => notify('Full medication history opened')}>Open medication history <ArrowRight size={15}/></button>
        </div></details>
      </div>

      <details className="card history-disclosure"><summary><span><ClipboardCheck size={20}/><b>Long-term clinical history</b><small>Timeline, procedures, previous results and resolved conditions</small></span><ChevronDown size={19}/></summary><Timeline compact/></details>
    </div>

    <aside className="doctor-rail">
      <section className="card consultation-card"><span className="eyebrow"><Stethoscope size={14}/> CONSULTATION</span><h3>Suggested review</h3><p>Decision support based on available evidence. Confirm independently.</p>
        {['Examine for oedema and heart failure signs','Confirm all medicines and actual doses','Review renal function and anaemia','Discuss glycaemic control'].map((x,i)=><label key={x}><input type="checkbox"/><span><b>{i+1}</b>{x}</span></label>)}
        <button className="btn primary full" onClick={() => notify('Draft plan created for clinician review')}>Start consultation plan <ArrowRight size={17}/></button>
      </section>
      <section className="card quick-facts"><div className="readable-title"><span className="title-icon blue"><CircleUserRound size={20}/></span><div><h3>Key background</h3></div></div>
        <dl><div><dt>Conditions</dt><dd>Diabetes · Hypertension · Dyslipidaemia</dd></div><div><dt>Allergies</dt><dd className="danger-text">Penicillin</dd></div><div><dt>Renal function</dt><dd>eGFR 62 mL/min</dd></div><div><dt>Smoking</dt><dd>Never</dd></div><div><dt>Alcohol</dt><dd>Occasional</dd></div></dl>
      </section>
      <button className="quiet-action" onClick={() => notify('All source records opened')}><FileText size={18}/> View all 12 source records <ArrowRight size={16}/></button>
    </aside>
  </div>
  {detail && <div className="detail-backdrop" onClick={() => setDetail(null)}><aside className="detail-drawer" onClick={e => e.stopPropagation()}><button className="drawer-close" onClick={() => setDetail(null)}><X size={20}/></button><PriorityDetail type={detail}/></aside></div>}
</div>}

function PriorityDetail({type}) {
  const content = {
    dose: { tag:'Medication discrepancy', title:'Confirm the actual amlodipine dose', lead:'Two recent sources show different strengths.', facts:[['Cardiology note · 12 Aug 2026','Amlodipine increased to 10 mg once daily'],['Medicine-strip photo · Uploaded today','Packaging appears to show 5 mg; image needs confirmation']], note:'Verify the strip, adherence and current dose directly with the patient before prescribing.' },
    symptom: { tag:'New patient-reported symptom', title:'Fatigue with bilateral ankle swelling', lead:'Progressive symptoms reported over the last 3 weeks.', facts:[['Relevant observations','BP 154/94 · Weight 86.2 kg · BMI 29.1'],['Relevant history','Hypertension · Diabetes · eGFR 62 mL/min']], note:'Assess onset, severity, associated dyspnoea, orthopnoea, urine output and examination findings.' },
    renal: { tag:'Overdue follow-up', title:'Repeat renal function result not found', lead:'The expected follow-up document is absent from available records.', facts:[['Cardiology plan · 12 Aug 2026','Repeat renal function within 4 weeks'],['Latest available panel · 09 Aug 2026','eGFR 62 mL/min']], note:'Ask whether testing was completed elsewhere before ordering a duplicate investigation.' },
  }[type];
  return <><span className="drawer-tag">{content.tag}</span><h2>{content.title}</h2><p className="drawer-lead">{content.lead}</p><div className="drawer-facts">{content.facts.map(([label,value])=><div key={label}><small>{label}</small><strong>{value}</strong></div>)}</div><div className="drawer-note"><Stethoscope size={18}/><p>{content.note}</p></div><button className="btn primary full">Add to consultation plan</button></>;
}

function PatientView({records,onUpload,notify}) { const [step,setStep]=useState(2); return <div className="patient-page">
  <div className="intake-top"><div><span className="eyebrow">PRE-VISIT CHECK-IN</span><h1>Help your doctor understand your health</h1><p>Add what you have—even a photo of a medicine strip helps. You can skip anything you don’t know.</p></div><div className="appointment"><CalendarDays size={20}/><span><small>Appointment</small><strong>Today, 4:30 PM</strong><em>Dr. Rhea Menon</em></span></div></div>
  <div className="stepper">{['About you','Your records','Symptoms','Review'].map((s,i)=><button key={s} className={step===i+1?'active':step>i+1?'done':''} onClick={()=>setStep(i+1)}><span>{step>i+1?<Check size={15}/>:i+1}</span><label>{s}</label></button>)}</div>
  {step===1 && <div className="intake-card card"><h2>Tell us about you</h2><p>This helps match records to the right person.</p><div className="form-grid"><Field label="Full name" value="Arun Kumar"/><Field label="Date of birth" value="14 March 1968"/><Field label="Phone number" value="+91 98765 43210"/><Field label="Blood group" value="B+"/></div><button className="btn primary next" onClick={()=>setStep(2)}>Continue <ArrowRight size={17}/></button></div>}
  {step===2 && <div className="intake-card card"><div className="intake-heading"><div><h2>Add your medical records</h2><p>Upload prescriptions, test reports, scans, discharge summaries, or medicine photos.</p></div><span className="safe"><ShieldCheck size={16}/> Private & secure</span></div>
    <button className="dropzone" onClick={onUpload}><div><UploadCloud size={29}/></div><strong>Choose files or take a photo</strong><span>PDF, JPG, PNG or DOC · Up to 20 MB each</span><em><FilePlus2 size={16}/> Add records</em></button>
    <div className="help-cards"><div><FileText size={20}/><span><strong>Have medical documents?</strong><small>Upload consultations, tests, scans or prescriptions.</small></span></div><div><Pill size={20}/><span><strong>Only have medicine strips?</strong><small>Take clear photos of the front and back.</small></span></div><div><AlertCircle size={20}/><span><strong>Something is missing?</strong><small>That’s okay. Tell us what you remember next.</small></span></div></div>
    <h3 className="uploaded-title">Added records <span>{records.length}</span></h3><div className="upload-list">{records.slice(0,4).map(r=><div key={r.id}><span className={`file-icon ${r.tone}`}><r.icon size={18}/></span><span><strong>{r.name}</strong><small>{r.type} · {r.date}</small></span><span className={r.status==='analysed'?'analysed':'review'}>{r.status==='analysed'?<><CheckCircle2 size={14}/> Ready</>:<><Clock3 size={14}/> Reviewing</>}</span><button><X size={16}/></button></div>)}</div>
    <div className="intake-actions"><button className="btn secondary" onClick={()=>setStep(1)}><ArrowLeft size={16}/> Back</button><button className="btn primary" onClick={()=>setStep(3)}>Continue to symptoms <ArrowRight size={16}/></button></div>
  </div>}
  {step===3 && <div className="intake-card card"><h2>What brings you to the doctor?</h2><p>Describe the main concern in your own words.</p><label className="textarea-label">Main symptoms<textarea defaultValue="Feeling very tired for the last few weeks, and both ankles become swollen by evening."/></label><div className="form-grid"><Field label="When did it start?" value="About 3 weeks ago"/><Field label="Is it getting worse?" value="Gradually getting worse"/></div><label className="textarea-label">Anything else your doctor should know?<textarea placeholder="For example: a medicine you stopped, an allergy, or a previous treatment..."/></label><div className="intake-actions"><button className="btn secondary" onClick={()=>setStep(2)}>Back</button><button className="btn primary" onClick={()=>setStep(4)}>Review information <ArrowRight size={16}/></button></div></div>}
  {step===4 && <div className="intake-card card review-card"><div className="success-icon"><Check size={25}/></div><h2>You’re ready for your appointment</h2><p>Your information will be organised for your doctor. They will verify it with you before making any clinical decisions.</p><div className="review-summary"><div><CircleUserRound size={20}/><span><strong>Personal details</strong><small>Complete</small></span><CheckCircle2 size={18}/></div><div><FileText size={20}/><span><strong>Medical records</strong><small>{records.length} files added</small></span><CheckCircle2 size={18}/></div><div><MessageSquareText size={20}/><span><strong>Current symptoms</strong><small>Added</small></span><CheckCircle2 size={18}/></div></div><button className="btn primary full" onClick={()=>notify('Check-in submitted to Dr. Rhea Menon')}>Submit check-in</button><button className="text-center" onClick={()=>setStep(2)}>Edit my information</button></div>}
  <p className="patient-disclaimer"><ShieldCheck size={15}/> DocPilot organises your information for your clinician. It does not diagnose or replace medical advice.</p>
</div>}

const Stat=({label,value,sub,warn,danger})=><div><span>{label}</span><strong>{value}</strong><small className={danger?'danger':warn?'warn':''}>{sub}</small></div>;
const Condition=({name,meta,tag,tone})=><div className="condition"><span className={`condition-dot ${tone}`}/><span><strong>{name}</strong><small>{meta}</small></span><em className={tone}>{tag}</em><ChevronDown size={16}/></div>;
const Medicine=({name,dose,verified})=><div className="medicine"><span className="pill-icon"><Pill size={16}/></span><span><strong>{name}</strong><small>{dose}</small></span>{verified?<em className="verified"><CheckCircle2 size={14}/> Verified</em>:<em className="unverified"><AlertCircle size={14}/> Verify</em>}</div>;
const Attention=({tone,title,body,action})=><div className={`attention-item ${tone}`}><span><AlertCircle size={17}/></span><div><strong>{title}</strong><p>{body}</p><button>{action} <ArrowRight size={13}/></button></div></div>;
const Vital=({value,unit,label,tone})=><div><strong className={tone||''}>{value} <small>{unit}</small></strong><span>{label}</span></div>;
const Field=({label,value})=><label className="field">{label}<input defaultValue={value}/></label>;

function AvatarImage({src, initials, alt, className=''}) {
  const [failed, setFailed] = useState(!src);
  return failed
    ? <span className={`avatar-image avatar-fallback ${className}`} aria-label={alt}>{initials}</span>
    : <img className={`avatar-image ${className}`} src={src} alt={alt} onError={() => setFailed(true)}/>;
}

function Timeline({compact=false}) { const data=compact?timeline.slice(0,3):timeline; return <div className={`timeline ${compact?'compact':''}`}>{data.map((x,i)=><div className="timeline-item" key={i}><span className={`timeline-dot ${x.tone}`}/><div className="timeline-date">{x.date}</div><div><span className={`tag ${x.tone}`}>{x.tag}</span><h4>{x.title}</h4><p>{x.body}</p></div></div>)}</div> }
function Records({records,search,setSearch,onUpload}) { return <div className="records-page card"><div className="records-tools"><div><h2>All medical records</h2><p>Documents and images provided for this patient.</p></div><button className="btn primary" onClick={onUpload}><UploadCloud size={16}/> Add records</button></div><div className="search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search records..."/></div><div className="records-table">{records.map(r=><div key={r.id}><span className={`file-icon ${r.tone}`}><r.icon size={19}/></span><span><strong>{r.name}</strong><small>{r.type}</small></span><span>{r.date}</span><em className={r.status==='analysed'?'verified':'unverified'}>{r.status==='analysed'?'Analysed':'Needs review'}</em><button><MoreHorizontal size={18}/></button></div>)}</div></div> }
function Gaps({notify}) { return <div className="gaps-page"><div className="card gap-hero"><span><AlertCircle size={22}/></span><div><h2>Missing information can change the clinical picture</h2><p>These gaps were identified from previous plans and the patient’s current account. Confirm with the patient before relying on them.</p></div></div>{[{title:'Latest ECG report',meta:'Recommended in cardiology note · 12 Aug 2026',why:'May help assess reported fatigue and ankle swelling.',level:'High priority'},{title:'Repeat renal function panel',meta:'Due around 09 Sep 2026 · No result found',why:'Required after medication adjustment and reduced eGFR.',level:'Follow-up overdue'}].map(g=><div className="card gap-row" key={g.title}><span className="gap-icon"><FileText size={21}/></span><div><em>{g.level}</em><h3>{g.title}</h3><p>{g.meta}</p><small><strong>Why it matters:</strong> {g.why}</small></div><button className="btn secondary" onClick={()=>notify(`Request prepared: ${g.title}`)}>Request record</button></div>)}</div> }

function toUiRecord(record) {
  const image = record.content_type?.startsWith('image/');
  return {
    id: record.id,
    name: record.filename,
    date: record.captured_at || new Date(record.uploaded_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
    type: record.source_type.replaceAll('_', ' '),
    status: record.status === 'ready' ? 'analysed' : 'review',
    icon: image ? FileImage : FileText,
    tone: image ? 'orange' : 'blue',
  };
}

createRoot(document.getElementById('root')).render(<App/>);
