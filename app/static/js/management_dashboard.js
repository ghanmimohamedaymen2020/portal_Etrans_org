// Fonctions pour gérer l'indicateur de chargement
function showLoading(message = 'Chargement des données...') {
  const overlay = document.getElementById('loading-overlay');
  const messageEl = document.getElementById('loading-message');
  if (overlay) {
    messageEl.textContent = message;
    overlay.classList.remove('hidden');
  }
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) {
    overlay.classList.add('hidden');
  }
}

// Indicateur de chargement pour les opérations longues
function withLoading(fn, message = 'Chargement...') {
  return async function(...args) {
    try {
      showLoading(message);
      return await fn(...args);
    } finally {
      hideLoading();
    }
  };
}

document.addEventListener('DOMContentLoaded',function(){
  // Afficher le chargement si on est en mode liste
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('listOnly')) {
    showLoading('Chargement de la liste des factures...');
  }
  
  // Masquer le chargement après 2 secondes maximum (au cas où)
  setTimeout(hideLoading, 2000);
/* Lines 2951-2953 omitted */
  const listTitle=document.getElementById('list-title');
  const listCount=document.getElementById('list-count');
  const listTableBody=document.querySelector('#list-table tbody');
  const listHeaderRow=document.getElementById('list-header-row');
  const listSearch=document.getElementById('list-search');
  const listPageSize=document.getElementById('list-page-size');
  const listPagePrev=document.getElementById('list-page-prev');
  const listPageNext=document.getElementById('list-page-next');
  const listPageInfo=document.getElementById('list-page-info');
  const listLoading=document.getElementById('list-loading');
  const exportCsvBtn=document.getElementById('export-csv-btn');
  const listBack=document.getElementById('list-back');
  const columnToggleBtn=document.getElementById('column-toggle-btn');
  const columnMenu=document.getElementById('column-menu');
  const currencyContainer=document.getElementById('currency-container');
  const deviseChartCanvas=document.getElementById('deviseChart');
  const deviseCommercialBody=document.getElementById('devise-commercial-body');
  const deviseCommercialFilter=document.getElementById('devise-commercial-filter');
  let currentListKey=null;
  let currentItems=[];
  let currentColumns=[];
  let hiddenColumns=new Set();
  let currentPage=1;
  let listMode='summary';
  let commercialFilter=null;
  let deviseChart=null;
  let invoiceHeaderMap = new Map();
  // Global cache for monthly activity (shared across functions)
  window.monthlyActivityCache = window.monthlyActivityCache || null;

  function normalizeInvoiceRef(v){
    try{ return String(v||'').replace(/\s+/g,'').toUpperCase(); }catch(e){ return ''; }
  }

  function extractCommercialFromItem(item){
    if(!item) return '';
    return item.nom_commercial || item.id_commercial || item.FF_H_IdCommercial || item.AA_H_IdCommercial || item.AA_H_NomCommercial || '';
  }

  function rebuildInvoiceHeaderMap(items){
    invoiceHeaderMap = new Map();
    (items || []).forEach(item => {
      const refs = [
        item && (item.reference ?? item.FF_H_NumFact ?? item.AA_H_Reference ?? item.AA_H_NumFacture),
        item && item.invoice_num
      ];
      refs.forEach(ref => {
        const key = normalizeInvoiceRef(ref);
        if(!key) return;
        const existing = invoiceHeaderMap.get(key);
        if(!existing){
          invoiceHeaderMap.set(key, item);
          return;
        }
        const exCom = String(extractCommercialFromItem(existing) || '').trim();
        const nwCom = String(extractCommercialFromItem(item) || '').trim();
        if(!exCom && nwCom){
          invoiceHeaderMap.set(key, item);
        }
      });
    });
  }

  // Simple HTML-escape helper for title attributes
  function escapeHtml(s){
    if(s===null||s===undefined) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function storageKey(){
    return `mgmt_hidden_cols_${currentListKey||'default'}`;
  }

  function loadHiddenColumns(){
    try{
      const raw=localStorage.getItem(storageKey());
      if(!raw) return new Set();
      const arr=JSON.parse(raw);
      return new Set(Array.isArray(arr)?arr:[]);
    }catch{
      return new Set();
    }
  }

  function saveHiddenColumns(){
    try{
      localStorage.setItem(storageKey(),JSON.stringify(Array.from(hiddenColumns)));
    }catch{}
  }

  const columnSets={
    freightSummary:[
      {key:'commercial',label:'Commercial'},
      {key:'count',label:'Nombre'},
      {key:'total_achat',label:'Total Achat'},
      {key:'total_vente',label:'Total Vente'},
      {key:'total_marge',label:'Total Marge'}
    ],
    freightDetails:[
      {key:'devise',label:'Devise'},
      {key:'dossier',label:'Dossier'},
      {key:'house',label:'House'},
      {key:'mont_achat',label:'Mont Achat'},
      {key:'mont_vente',label:'Mont Vente'},
      {key:'marge',label:'Marge'},
      {key:'eta',label:'ETA'},
      {key:'fournisseur',label:'Fournisseur'},
      {key:'reference_aa',label:'Référence AA'},
      {key:'date_creation',label:'Date Création'},
      {key:'id_utilisateur',label:'Id Utilisateur'},
      {key:'email_utilisateur',label:'Email Utilisateur'}
    ],
    freightCommercialDetails:[
      {key:'dossier',label:'Dossier'},
      {key:'house',label:'House'},
      {key:'devise',label:'Devise'},
      {key:'mont_achat',label:'Mont Achat'},
      {key:'mont_vente',label:'Mont Vente'},
      {key:'marge',label:'Marge'},
      {key:'eta',label:'ETA'},
      {key:'fournisseur',label:'Fournisseur'},
      {key:'reference_aa',label:'Référence AA'},
      {key:'date_creation',label:'Date Création'}
    ],
    invoices:[
      {key:'reference',label:'Numéro facture'},
      {key:'date_process',label:'Date Process'},
      {key:'dossier',label:'Dossier'},
      {key:'nom_client',label:'Agent'},
      {key:'eta',label:'ETA'},
      {key:'house',label:'House'},
      {key:'cont_info',label:'Conteneur'},
      {key:'service',label:'Service'},
      {key:'nom_commercial',label:'Nom Commercial'},
      {key:'ff_total_non_soumis',label:'Total Non Soumis'},
      {key:'ff_total_soumis',label:'Total Soumis'},
      {key:'ff_total_tva',label:'Total TVA'},
      {key:'total_ttc',label:'Total TTC'},
      {key:'devise',label:'Devise'}
    ],
    invoicesAgent:[
      {key:'reference',label:'Numéro facture'},
      {key:'date_process',label:'Date Process'},
      {key:'dossier',label:'Dossier'},
      {key:'nom_client',label:'Agent'},
      {key:'eta',label:'ETA'},
      {key:'house',label:'House'},
      {key:'service',label:'Service'},
      {key:'ff_total_non_soumis',label:'Total Non Soumis'},
      {key:'ff_total_soumis',label:'Total Soumis'},
      {key:'ff_total_tva',label:'Total TVA'},
      {key:'total_ttc',label:'Total TTC'},
      {key:'devise',label:'Devise'}
    ],
    aaSansFacture:[
      {key:'AA_H_Reference',label:'Numéro Avis'},
      {key:'AA_H_DateProcess',label:'Date Process'},
      {key:'AA_H_Dossier',label:'Dossier'},
      {key:'AA_H_NomClient',label:'Client'},
      {key:'AA_H_Adresse_1',label:'Adresse 1'},
      {key:'AA_H_Adresse_2',label:'Adresse 2'},
      {key:'AA_H_Adresse_3',label:'Adresse 3'},
      {key:'AA_H_TVA',label:'Matricule Fiscale'},
      {key:'AA_H_DateSuspTVA_Du',label:'Susp TVA Du'},
      {key:'AA_H_DateSuspTVA_Au',label:'Susp TVA Au'},
      {key:'AA_H_IdBar',label:'ID Bar'},
      {key:'AA_H_Voyage',label:'Voyage'},
      {key:'AA_H_Navire',label:'Navire'},
      {key:'AA_H_PPOL',label:'PPOL'},
      {key:'AA_H_POL',label:'POL'},
      {key:'AA_H_DPOL',label:'DPOL'},
      {key:'AA_H_PPOD',label:'PPOD'},
      {key:'AA_H_POD',label:'POD'},
      {key:'AA_H_DPOD',label:'DPOD'},
      {key:'AA_H_ETA',label:'ETA'},
      {key:'AA_H_Traduccion',label:'Traduction'},
      {key:'AA_H_House',label:'House'},
      {key:'AA_H_MasterBL',label:'MasterBL'},
      {key:'AA_H_Service',label:'Service'},
      {key:'AA_H_Escale',label:'Escale'},
      {key:'AA_H_Rubrique',label:'Rubrique'},
      {key:'AA_H_IdCommercial',label:'ID Commercial'},
      {key:'nom_commercial',label:'Nom Commercial'},
     // {key:'AA_H_NomCommercial',label:'Nom Commercial (raw)'},
      {key:'AA_H_EmailCommercial',label:'Email Commercial'},
      {key:'AA_H_IdUtilisateur',label:'ID Utilisateur'},
      {key:'AA_H_EmailUtilisateur',label:'Email Utilisateur'},
      //{key:'AA_H_Trans_PC_ClientFinal',label:'Client Final'},
      {key:'AA_H_NomClientFinal',label:'Nom Client Final'},
      {key:'AA_H_NumSuspTVA',label:'Num Susp TVA'},
      {key:'AA_H_NumFacture',label:'Num Facture'},
      {key:'aa_total_non_soumis',label:'Total Non Soumis'},
      {key:'aa_total_soumis',label:'Total Soumis'},
      {key:'aa_total_tva',label:'Total TVA'},
      {key:'aa_total_general',label:'Total Général'},
      {key:'aa_total_ttc',label:'Total TTC'}
    ],
    default:[
      {key:'reference',label:'Numéro facture'},
      {key:'dossier',label:'Dossier'},
      {key:'type',label:'Type'},
      {key:'libelle',label:'Libellé'},
      {key:'montant',label:'Montant'},
      {key:'devise',label:'Devise'}
    ]
  };

  const listData={
    generated:{
      title:'Total marge sur fret',
      statusClass:'status-info',
      columns:columnSets.freightSummary,
      items:[]
    },
    'not-stamped':{
      title:'Avis non timbrés',
      statusClass:'status-danger',
      columns:columnSets.aaSansFacture,
      items:[]
    },
    'not-withdrawn':{
      title:'Marchandises non retirées',
      statusClass:'status-warning',
      columns:columnSets.default,
      items:[
        {reference:'MG-0441',dossier:'DOS-100',type:'Magasinage',libelle:'Non retiré',montant:'0',devise:'TND'},
        {reference:'MG-0442',dossier:'DOS-101',type:'Magasinage',libelle:'Non retiré',montant:'0',devise:'TND'}
      ]
    },
    invoices:{
      title:'Liste des factures (mois)',
      statusClass:'status-success',
      columns:columnSets.invoices,
      items:[]
    },
  };

  const listCache={};

  function renderColumns(columns){
    listHeaderRow.innerHTML='';
    currentColumns=columns;
    hiddenColumns=loadHiddenColumns();
    columns.forEach(col=>{
      const th=document.createElement('th');
      th.textContent=col.label;
      th.setAttribute('data-col',col.key);
      if(hiddenColumns.has(col.key)){
        th.classList.add('hidden-col');
      }
      listHeaderRow.appendChild(th);
    });
    renderColumnMenu(columns);
      try{ if(typeof makeTablesSortable==='function') makeTablesSortable(); }catch(e){}
  }

  function renderColumnMenu(columns){
    if(!columnMenu) return;
    columnMenu.innerHTML='';
    columns.forEach(col=>{
      const item=document.createElement('label');
      item.className='column-item';
      const checkbox=document.createElement('input');
      checkbox.type='checkbox';
      checkbox.checked=!hiddenColumns.has(col.key);
      checkbox.dataset.key=col.key;
      checkbox.addEventListener('change',function(){
        toggleColumn(this.dataset.key,this.checked);
      });
      const span=document.createElement('span');
      span.textContent=col.label;
      item.appendChild(checkbox);
      item.appendChild(span);
      columnMenu.appendChild(item);
    });
  }

  function toggleColumn(key,visible){
    if(!key) return;
    if(visible){
      hiddenColumns.delete(key);
    }else{
      hiddenColumns.add(key);
    }
    document.querySelectorAll(`[data-col="${key}"]`).forEach(el=>{
      el.classList.toggle('hidden-col',!visible);
    });
    saveHiddenColumns();
  }

  async function fetchInvoices(){
    if(listCache.invoices) return listCache.invoices;
    const response=await fetch('/api/factures/aa-detail?limit=0');
    const ct=(response.headers.get('content-type')||'').toLowerCase();
    if(!ct.includes('application/json')){
      throw new Error('Authentification requise ou réponse inattendue (html)');
    }
    const data=await response.json();
    if(!response.ok){
      throw new Error(data.error||'Erreur API');
    }
    listCache.invoices=data.factures||[];
    return listCache.invoices;
  }

  async function fetchFreightItems(){
    if(listCache.freight) return listCache.freight;
    const response=await fetch('/api/freight/items');
    const ct=(response.headers.get('content-type')||'').toLowerCase();
    if(!ct.includes('application/json')){
      throw new Error('Authentification requise ou réponse inattendue (html)');
    }
    const data=await response.json();
    if(!response.ok){
      throw new Error(data.error||'Erreur API');
    }
    listCache.freight=data.items||[];
    return listCache.freight;
  }

  function setKpiValue(key,value){
    const el=document.querySelector(`[data-kpi-value="${key}"]`);
    if(el){
      el.textContent=value;
    }
  }

  function formatDateValue(value){
    if(!value) return value;
    const date=new Date(value);
    if(Number.isNaN(date.getTime())) return value;
    const dd=String(date.getDate()).padStart(2,'0');
    const mm=String(date.getMonth()+1).padStart(2,'0');
    const yyyy=date.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
  }

  function formatAmount(value){
    const number=Number(value)||0;
    return number.toLocaleString('fr-FR',{
      minimumFractionDigits:3,
      maximumFractionDigits:3
    });
  }

  // Truncate long text for table cells (preserve full value in title)
  function truncateString(s, maxLen){
    try{
      if(s===null||s===undefined) return '';
      const str = String(s);
      if(str.length <= (maxLen||50)) return str;
      return str.slice(0, (maxLen||50) - 3) + '...';
    }catch(e){ return s; }
  }

  function renderDeviseCommercialSummary(items,deviseFilter=null,monthIndex=null,year=null){
    if(!deviseCommercialBody) return;
    const grouped=new Map();
    const monthNames=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc'];
    items.forEach(item=>{
      const devise=item.devise||'N/A';
      if(deviseFilter&&devise!==deviseFilter) return;
      const commercial=item.email_utilisateur||item.id_utilisateur||'Non assigné';
      const key=`${devise}||${commercial}`;
      if(!grouped.has(key)){
        grouped.set(key,{
          devise,
          commercial,
          total_achat:0,
          total_vente:0,
          total_marge:0
        });
      }
      const row=grouped.get(key);
      const achat=Number(item.mont_achat)||0;
      const vente=Number(item.mont_vente)||0;
      row.total_achat+=achat;
      row.total_vente+=vente;
      row.total_marge+=vente-achat;
    });
    const data=Array.from(grouped.values()).sort((a,b)=>{
      const byDevise=a.devise.localeCompare(b.devise,'fr');
      if(byDevise!==0) return byDevise;
      return a.commercial.localeCompare(b.commercial,'fr');
    });
    if(deviseCommercialFilter){
      let txt='';
      if(deviseFilter) txt+=`Devise: ${deviseFilter}`;
      if(monthIndex!==null){
        if(txt) txt+= ' — ';
        txt+= `${monthNames[monthIndex]}` + (year?` ${year}`:'');
      }
      deviseCommercialFilter.textContent=txt;
    }
    if(!data.length){
      deviseCommercialBody.innerHTML=`
        <tr>
          <td colspan="5">Aucune donnée disponible</td>
        </tr>
      `;
      return;
    }
    deviseCommercialBody.innerHTML=data.map(row=>`
      <tr class="commercial-row" data-commercial="${row.commercial}">
        <td>${row.devise}</td>
        <td data-commercial="${row.commercial}">${row.commercial}</td>
        <td>${formatAmount(row.total_achat)}</td>
        <td>${formatAmount(row.total_vente)}</td>
        <td>${formatAmount(row.total_marge)}</td>
      </tr>
    `).join('');
    // clicking the row opens the commercial details in a new tab
    deviseCommercialBody.querySelectorAll('.commercial-row').forEach(row=>{
      row.addEventListener('click',function(){
        const commercial=this.getAttribute('data-commercial');
        if(!commercial) return;
        const url=new URL(window.location.href);
        url.searchParams.set('list','generated');
        url.searchParams.set('listOnly','1');
        url.searchParams.set('commercial',commercial);
        window.open(url.toString(),'_blank');
      });
    });
  }

  async function renderList(key, opts={}){
    const data=listData[key];
    if(!data) return;
    currentListKey=key;
    currentPage=1;
    listMode=key==='generated'?'summary':'detail';
    commercialFilter=null;
    if(listBack) listBack.style.display='none';
    if(key==='generated'){
      hiddenColumns=new Set();
      saveHiddenColumns();
    }
    listTitle.textContent=data.title;
    // If showing invoices, append the month/year to the title
    if(key==='invoices'){
      let usedMonth=null;
      let usedYear=null;
      if(opts && typeof opts.month!=='undefined' && opts.month!==null) usedMonth=Number(opts.month);
      if(opts && typeof opts.year!=='undefined' && opts.year!==null) usedYear=Number(opts.year);
      const now=new Date();
      if(usedMonth===null) usedMonth=now.getMonth()+1;
      if(usedYear===null) usedYear=now.getFullYear();
      const monthNamesFull=['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'];
      const baseTitle=(data.title||'').replace('(mois)','').trim();
      // map type code to human-readable label when provided in opts
      const typeMap = { 'T':'Timbrage', 'M':'Magasinage', 'S':'Surestarie', 'A':'Agent' };
      const typeCode = opts && opts.type ? String(opts.type).toUpperCase() : null;
      const typeLabel = typeCode && typeMap[typeCode] ? ` ${typeMap[typeCode]}` : '';
      listTitle.textContent=`${baseTitle}${typeLabel} ${monthNamesFull[usedMonth-1]} ${usedYear}`;
    }
    listTableBody.innerHTML='';
    let columns = key==='generated'?columnSets.freightSummary:(data.columns||columnSets.default);
    // if invoices list and a type filter is provided, choose a matching column set
    if(key==='invoices'){
      const t = opts && opts.type ? String(opts.type).toUpperCase() : null;
      if(t === 'A') columns = columnSets.invoicesAgent;
    }
    renderColumns(columns);
    let items=data.items||[];
        if(key==='not-stamped'||key==='invoices'){
      try{
        if(listLoading) listLoading.classList.add('visible');
            if(key==='invoices'){
              // fetch FF-based invoices used by charts for the selected month/year
              let monthFilter=null;
              let yearFilter=null;
              if(opts && typeof opts.month!=='undefined' && opts.month!==null){
                monthFilter=Number(opts.month); // 1-based month
              }
              if(opts && typeof opts.year!=='undefined' && opts.year!==null){
                yearFilter=Number(opts.year);
              }
              if(monthFilter===null || yearFilter===null){
                const now=new Date();
                if(monthFilter===null) monthFilter=now.getMonth()+1;
                if(yearFilter===null) yearFilter=now.getFullYear();
              }
              let fetchUrl = `/api/factures/ff-list?month=${monthFilter}&year=${yearFilter}`;
              if(opts && opts.type){
                fetchUrl += `&type=${encodeURIComponent(opts.type)}`;
              }
              if(opts && opts.currency){
                fetchUrl += `&currency=${encodeURIComponent(opts.currency)}`;
              }
              const resp = await fetch(fetchUrl);
              const data = await resp.json();
              if(!resp.ok) throw new Error(data.error||'Erreur API');
              items = data.factures || [];
              // show export button for invoices and bind download
                if(exportCsvBtn && window.PERMS && window.PERMS.exportCsv){
                exportCsvBtn.style.display='inline-block';
                exportCsvBtn.onclick = function(){
                  let url = `/api/factures/ff-list/export?month=${monthFilter}&year=${yearFilter}`;
                  if(opts && opts.type) url += `&type=${encodeURIComponent(opts.type)}`;
                  window.location = url;
                };
              }
            } else {
              items=await fetchInvoices();
            }
        if(key==='not-stamped'){
          // enable XLSX export for not-stamped list
          if(exportCsvBtn && window.PERMS && window.PERMS.exportXlsx){
            exportCsvBtn.style.display='inline-block';
            exportCsvBtn.onclick = function(){
              window.location = '/api/factures/aa-detail/export.xlsx';
            };
          }
          setKpiValue('not-stamped',items.length);
        }
        // Filtrer les factures pour la liste 'invoices' (optionnel: mois/année)
        if(key==='invoices'){
          let monthFilter=null;
          let yearFilter=null;
          if(opts && typeof opts.month!=='undefined' && opts.month!==null){
            monthFilter=Number(opts.month); // 1-based month
          }
          if(opts && typeof opts.year!=='undefined' && opts.year!==null){
            yearFilter=Number(opts.year);
          }
          if(monthFilter===null || yearFilter===null){
            const now=new Date();
            if(monthFilter===null) monthFilter=now.getMonth()+1;
            if(yearFilter===null) yearFilter=now.getFullYear();
          }
          items=items.filter(it=>{
            if(!it.date_process) return false;
            const d=new Date(it.date_process);
            if(Number.isNaN(d.getTime())) return false;
            return d.getFullYear()===yearFilter && (d.getMonth()+1)===monthFilter;
          });
        }
      }catch(err){
        listTableBody.innerHTML=`
          <tr>
            <td colspan="${columns.length}">Erreur chargement:${err.message}</td>
          </tr>
        `;
        updateCount();
        if(listLoading) listLoading.classList.remove('visible');
        return;
      }finally{
        if(listLoading) listLoading.classList.remove('visible');
        hideLoading(); // Cacher l'indicateur de chargement global
      }
    }
    if(key==='generated'){
      try{
        if(listLoading) listLoading.classList.add('visible');
        items=await fetchFreightItems();
        // show export button for generated freight items
        if(exportCsvBtn){
          exportCsvBtn.style.display='inline-block';
          exportCsvBtn.onclick = function(){
            let url = `/api/freight/items/export`;
            window.location = url;
          };
        }
      }catch(err){
        listTableBody.innerHTML=`
          <tr>
            <td colspan="${columns.length}">Erreur chargement:${err.message}</td>
          </tr>
        `;
        updateCount();
        if(listLoading) listLoading.classList.remove('visible');
        return;
      }finally{
        if(listLoading) listLoading.classList.remove('visible');
        hideLoading();
      }
    }
    if(key==='generated'){
      const grouped=new Map();
      items.forEach(item=>{
        const commercial=item.email_utilisateur||item.id_utilisateur||'Non assigné';
        if(!grouped.has(commercial)){
          grouped.set(commercial,{
            commercial,
            count:0,
            total_achat:0,
            total_vente:0,
            total_marge:0
          });
        }
        const row=grouped.get(commercial);
        const achat=Number(item.mont_achat)||0;
        const vente=Number(item.mont_vente)||0;
        row.count+=1;
        row.total_achat+=achat;
        row.total_vente+=vente;
        row.total_marge+=(vente-achat);
      });
      currentItems=Array.from(grouped.values());
      currentColumns=columnSets.freightSummary;
      renderColumns(currentColumns);
    }else{
      currentItems=items;
    }
    // hide export button for lists that don't support export (allow invoices, generated and not-stamped)
    if(exportCsvBtn && !['invoices','generated','not-stamped'].includes(key)) exportCsvBtn.style.display='none';
    if(!items.length){
      listTableBody.innerHTML=`
        <tr>
          <td colspan="${columns.length}">Aucune donnée</td>
        </tr>
      `;
      updateCount();
      return;
    }
    applySearchFilter();
    hideLoading(); // S'assurer que le chargement est caché à la fin
  }

  async function initKpiCounts(){
    try{
      // Get aggregated totals/count for Avis non timbrés
      try{
        const aaResp = await fetch('/api/factures/aa-totals', { credentials: 'include' });
        if (aaResp.ok) {
          const aaJson = await aaResp.json();
          const cnt = aaJson.count || 0;
          // Prefer explicit `total_general` from the API when available,
          // otherwise fall back to summing submitted + non-submitted totals.
          const total_sum = (aaJson.total_general != null)
            ? Number(aaJson.total_general || 0)
            : (Number(aaJson.total_soumis || 0) + Number(aaJson.total_non_soumis || 0));
          setKpiValue('not-stamped', formatAmount(total_sum) + ' TND');
          const badge = document.querySelector('[data-kpi-count="not-stamped-count"]');
          if (badge) badge.textContent = cnt;
        } else {
          // fallback to returning only a count
          try{
            const aaResp2 = await fetch('/api/factures/aa-detail?limit=0');
            const aaJson2 = await aaResp2.json();
            const aaCount = (aaJson2 && aaJson2.factures && aaJson2.factures.length) || aaJson2.total || 0;
            const badge = document.querySelector('[data-kpi-count="not-stamped-count"]'); if(badge) badge.textContent = aaCount;
            setKpiValue('not-stamped', '0 TND');
          }catch(e2){
            try{
              const totalResp = await fetch('/api/factures/count');
              const totalJson = await totalResp.json();
              const badge = document.querySelector('[data-kpi-count="not-stamped-count"]'); if(badge) badge.textContent = totalJson.count || 0;
            }catch(e3){}
            setKpiValue('not-stamped', '0 TND');
          }
        }
      }catch(e){
        console.warn('Erreur agrégat AA:', e);
        try{
          const totalResp = await fetch('/api/factures/count');
          const totalJson = await totalResp.json();
          const badge = document.querySelector('[data-kpi-count="not-stamped-count"]'); if(badge) badge.textContent = totalJson.count || 0;
        }catch(e2){}
        setKpiValue('not-stamped', '0 TND');
      }

      // Get current month Timbrage total (THT) for the 'invoices' KPI
      try{
        const now = new Date();
        const curYear = now.getFullYear();
        const curMonth = now.getMonth() + 1;
        // Replace any title markers '(mois)' with the current month name and year
        try{
          const monthNamesFull = ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'];
          document.querySelectorAll('.kpi-card .kpi-title').forEach(el=>{
            if(!el || !el.textContent) return;
            el.textContent = el.textContent.replace(/\(mois\)/i, `(${monthNamesFull[curMonth-1]} ${curYear})`);
          });
        }catch(e){ /* ignore DOM errors during initialisation */ }
        
        // Compute Timbrage KPI as ONLY (total_soumis + total_non_soumis)
        try {
          // First try server-side aggregate (preferred)
          const aggResp = await fetch(`/api/factures/ca-activite-total?year=${curYear}&month=${curMonth}&type=T`);
          if (aggResp.ok) {
            const agg = await aggResp.json();
            const sum = Number(agg.total_soumis || 0) + Number(agg.total_non_soumis || 0);
            setKpiValue('invoices', formatAmount(sum) + ' TND');
          } else {
            // Fallback: sum from detailed ff-list
            const listResp = await fetch(`/api/factures/ff-list?month=${curMonth}&year=${curYear}&type=T`);
            if (listResp.ok) {
              const listJson = await listResp.json();
              const rows = listJson.factures || [];
              let sumDetail = 0;
              rows.forEach(r => {
                const non = r.ff_total_non_soumis ?? r.FF_T_TotalNonSoumis ?? r.ff_t_totalnonsoumis ?? r.total_non_soumis ?? 0;
                const soum = r.ff_total_soumis ?? r.FF_T_TotalSoumis ?? r.ff_t_totalsoumis ?? r.total_soumis ?? 0;
                sumDetail += Number(non || 0) + Number(soum || 0);
              });
              setKpiValue('invoices', formatAmount(sumDetail) + ' TND');
            } else {
              setKpiValue('invoices', '0 TND');
            }
          }
        } catch(e) {
          console.warn('Erreur agrégat/detail Timbrage:', e);
          try {
            const listResp = await fetch(`/api/factures/ff-list?month=${curMonth}&year=${curYear}&type=T`);
            if (listResp.ok) {
              const listJson = await listResp.json();
              const rows = listJson.factures || [];
              let sumDetail = 0;
              rows.forEach(r => {
                const non = r.ff_total_non_soumis ?? r.FF_T_TotalNonSoumis ?? r.ff_t_totalnonsoumis ?? r.total_non_soumis ?? 0;
                const soum = r.ff_total_soumis ?? r.FF_T_TotalSoumis ?? r.ff_t_totalsoumis ?? r.total_soumis ?? 0;
                sumDetail += Number(non || 0) + Number(soum || 0);
              });
              setKpiValue('invoices', formatAmount(sumDetail) + ' TND');
            } else {
              setKpiValue('invoices', '0 TND');
            }
          } catch(e2) {
            setKpiValue('invoices', '0 TND');
          }
        }

        // Update Agent KPI title to current month (remove invoice count display)
        try{
          const monthNamesFull = ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'];
          const agentTitleEl = document.querySelector('.kpi-card[data-key="invoices-agent"] .kpi-title');
          if(agentTitleEl) agentTitleEl.textContent = `Factures - Agent (${monthNamesFull[curMonth-1]} ${curYear})`;
          const agentMainVal = document.querySelector('[data-kpi-value="invoices-agent"]');
          if(agentMainVal) agentMainVal.textContent = '';
        }catch(e){ /* ignore */ }
        // Récupérer totaux Agent par devise (EUR, USD) et afficher
        try{
          const atResp = await fetch(`/api/factures/agent-totals?month=${curMonth}&year=${curYear}`);
          if(atResp.ok){
            const atJson = await atResp.json();
            const totals = atJson.totals || {};
            const eur = Number(totals.EUR || 0);
            const usd = Number(totals.USD || 0);
            const eurEl = document.querySelector('[data-kpi-value="agent-eur"]');
            const usdEl = document.querySelector('[data-kpi-value="agent-usd"]');
            if(eurEl) eurEl.textContent = formatAmount(eur) + ' EUR';
            if(usdEl) usdEl.textContent = formatAmount(usd) + ' USD';
          }
        }catch(e){
          // ignore
        }
        
        // MAGASINAGE KPI — fetch totals and display
        try {
          const mResp = await fetch(`/api/factures/magasinage-totals?year=${curYear}&month=${curMonth}`, { credentials: 'include' });
          if (mResp.ok) {
            const mJson = await mResp.json();
            setKpiValue('invoices-magasinage', formatAmount(mJson.total_ttc || 0) + ' TND');
            setKpiValue('invoices-magasinage-tht-month', formatAmount(mJson.total_ht || 0) + ' TND');
            setKpiValue('invoices-magasinage-tht-year', formatAmount(mJson.total_year_ht || 0) + ' TND');
          }
        } catch(e) { console.error('Error fetching magasinage KPI', e); }
        
        // SURESTARIE KPI — fetch totals and display
        try {
          const sResp = await fetch(`/api/factures/surestarie-totals?year=${curYear}&month=${curMonth}`, { credentials: 'include' });
          if (sResp.ok) {
            const sJson = await sResp.json();
            setKpiValue('invoices-surestarie', formatAmount(sJson.total_ttc || 0) + ' TND');
            setKpiValue('invoices-surestarie-tht-month', formatAmount(sJson.total_ht || 0) + ' TND');
            setKpiValue('invoices-surestarie-tht-year', formatAmount(sJson.total_year_ht || 0) + ' TND');
          }
        } catch(e) { console.error('Error fetching surestarie KPI', e); }
        
        // ============================================
        // FREIGHT - Totaux mensuel et annuel
        // ============================================
        try{
          const now = new Date();
          const curYear = now.getFullYear();
          const freightResp = await fetch(`/api/freight/summary?year=${curYear}`);
          if(freightResp.ok){
            const freightJson = await freightResp.json();
            const total_du_mois = Number(freightJson.total_du_mois) || 0;
            const total_year = Number(freightJson.total_year) || 0;
            // show both values: month on main KPI, year in the small line below
            setKpiValue('generated', formatAmount(total_du_mois) + ' TND');
            const yearEl = document.querySelector('[data-kpi-value="generated-year"]');
            if(yearEl) yearEl.textContent = formatAmount(total_year) + ' TND';
          }
        } catch(e) { 
            console.error('Erreur chargement Freight:', e);
          }

        // Monthly activity reporting removed by user request — use empty cache
        window.monthlyActivityCache = {};
        
      } catch(e) {
        console.error('Erreur globale initKpiCounts:', e);
      }
    } catch(e) {
      console.error('Erreur fatale initKpiCounts:', e);
    }
  }

  function updateCount(visible,total){
    if(visible===total){
      listCount.textContent=`${total} élément(s)`;
    }else{
      listCount.textContent=`${visible}/${total} élément(s)`;
    }
  }

  function applySearchFilter(){
    const term=(listSearch.value||'').toLowerCase().trim();
    const size=parseInt(listPageSize.value,10);
    const columns=currentColumns.length?currentColumns:(listData[currentListKey]?.columns)||columnSets.default;
    rebuildInvoiceHeaderMap(currentItems);
    const filtered=currentItems.filter(item=>{
      if(!term) return true;
      const text=Object.values(item).join(' ').toLowerCase();
      return text.includes(term);
    });
    const totalPages=size>0?Math.max(1,Math.ceil(filtered.length/size)):1;
    if(currentPage>totalPages) currentPage=totalPages;
    if(currentPage<1) currentPage=1;
    const start=size>0?(currentPage-1)*size:0;
    const end=size>0?start+size:filtered.length;
    const limited=size>0?filtered.slice(start,end):filtered;
    listTableBody.innerHTML='';
    if(!limited.length){
      listTableBody.innerHTML=`
        <tr>
          <td colspan="${columns.length}">Aucune donnée</td>
        </tr>
      `;
      updateCount(0,filtered.length);
      updatePagination(0,filtered.length,totalPages);
      return;
    }
    limited.forEach(item=>{
      const tr=document.createElement('tr');
      tr.innerHTML=columns.map(col=>{
        let value=item[col.key]??'';
        // Fallback: ensure `nom_commercial` is shown even if the API returned a differently-named key
        if((col.key === 'nom_commercial' || (col.key||'').toString().toLowerCase() === 'nom_commercial') && (!value || value === '')){
          value = item['nom_commercial'] || item['id_commercial'] || item['FF_H_IdCommercial'] || item['AA_H_IdCommercial'] || item['AA_H_NomCommercial'] || item['AA_H_NOMCOMMERCIAL'] || item['aa_h_nomcommercial'] || '';
        }
        // format dates
        if(col.key && (col.key.toLowerCase().includes('date') || col.key.toLowerCase().includes('eta'))){
          value=formatDateValue(value);
        } else {
          // Avoid formatting certain string columns (house, dossier, reference, names)
          const noNumericFormat = new Set(['house','dossier','reference','nom_client','nom_commercial','eta','service','AA_H_House','AA_H_Dossier','AA_H_Reference','AA_H_NomClient','AA_H_NomCommercial','AA_H_MasterBL','AA_H_Escale','AA_H_Rubrique']);
          // For numeric-looking columns, format with formatAmount (3 decimals)
          const asNum = (value!==null && value!==undefined && value!=='' ) ? Number(value) : NaN;
          if(!Number.isNaN(asNum) && typeof value !== 'object' && !col.key.toLowerCase().includes('id') && !col.key.toLowerCase().includes('reference') && !noNumericFormat.has(col.key)){
            value = formatAmount(asNum);
          }
        }
        const hiddenClass=hiddenColumns.has(col.key)?'hidden-col':'';
        // Make invoice reference clickable to open invoice details
        let cellHtml = value;
        try{
          const keyLow = (col.key||'').toString().toLowerCase();
          if(/reference|numf|numfact|num_fact/i.test(col.key)){
            const inv = String(value||'').trim();
            if(inv){
              // mark AA header references so click handler can call AA detail endpoint directly
              const isAA = /AA_H_/i.test(col.key) || /AA_H_Reference/i.test(col.key);
              const aaAttr = isAA ? ' data-aa="1"' : '';
              const invLabel = truncateString(inv, 50);
              cellHtml = `<a href="#" class="invoice-link" data-invoice="${escapeHtml(inv)}"${aaAttr}>${escapeHtml(invLabel)}</a>`;
            }
          }
        }catch(e){ /* ignore formatting errors */ }
        const plainText = (value===null || value===undefined || typeof value==='object') ? '' : String(value);
        const displayText = truncateString(plainText, 50);
        // if the cellHtml is simple text (not an element), show truncated displayText
        let finalHtml = cellHtml;
        try{
          if(!/<[a-z][\s\S]*>/i.test(cellHtml)){
            finalHtml = escapeHtml(displayText);
          }
        }catch(e){ finalHtml = escapeHtml(displayText); }
        return `<td data-col="${col.key}" class="${hiddenClass}" title="${escapeHtml(plainText)}"><div class="cell-content">${finalHtml}</div></td>`;
      }).join('');
      if(currentListKey==='generated'&&listMode==='summary'){
        tr.classList.add('clickable-row');
        tr.addEventListener('click',function(){
          const commercial=item.commercial;
          if(!commercial) return;
          if(typeof showFreightByCommercial==='function'){
            showFreightByCommercial(commercial);
            document.body.classList.add('chart-only','show-chart-list');
          }
        });
      }
      listTableBody.appendChild(tr);
    });
    // Toggle compact rows: enable compact mode when the result set is large
    // Also enforce fixed row height when the result set is small (<20 rows)
    try{
      const table = document.getElementById('list-table');
      const tableContainer = document.querySelector('.table-responsive');
      const compact = filtered.length >= 20; // compact for 20+ rows
      const fixedRows = filtered.length < 20; // fixed height for small lists
      if(table){
        table.classList.toggle('compact-rows', compact);
        table.classList.toggle('fixed-rows', fixedRows);
      }
      if(tableContainer){
        tableContainer.classList.toggle('fixed-auto-height', fixedRows);
      }
    }catch(e){ }
    updateCount(limited.length,filtered.length);
    updatePagination(limited.length,filtered.length,totalPages);
  }

  function updatePagination(visible,total,totalPages){
    if(!listPageInfo||!listPagePrev||!listPageNext) return;
    const size=parseInt(listPageSize.value,10);
    if(size<=0||total===0){
      listPageInfo.textContent='';
      listPagePrev.disabled=true;
      listPageNext.disabled=true;
      return;
    }
    listPageInfo.textContent=`Page ${currentPage}/${totalPages}`;
    listPagePrev.disabled=currentPage<=1;
    listPageNext.disabled=currentPage>=totalPages;
  }

  document.querySelectorAll('.kpi-card').forEach(card=>{
    card.addEventListener('click',function(){
      document.querySelectorAll('.kpi-card').forEach(c=>c.classList.remove('active'));
      this.classList.add('active');
      const key=this.getAttribute('data-key');
      if(key==='generated'){
        const url=new URL(window.location.href);
        url.searchParams.set('chart','devise');
        url.searchParams.set('listOnly','1');
        window.open(url.toString(),'_blank');
        if(listSearch) listSearch.value='';
        return;
      }
      if(key){
        const url=new URL(window.location.href);
        // Make the new invoice-type KPIs behave like the original 'invoices' card
        if(key === 'invoices-agent'){
          url.searchParams.set('list','invoices');
          url.searchParams.set('type','A');
        } else if(key === 'invoices-surestarie'){
          url.searchParams.set('list','invoices');
          url.searchParams.set('type','S');
        } else if(key === 'invoices-magasinage'){
          url.searchParams.set('list','invoices');
          url.searchParams.set('type','M');
        } else {
          url.searchParams.set('list',key);
          // if this is the invoices KPI, prefilter to Timbrage
          if(key==='invoices'){
            url.searchParams.set('type','T');
          }
        }
        url.searchParams.set('listOnly','1');
        window.open(url.toString(),'_blank');
      }
      if(listSearch) listSearch.value='';
    });
  });

  // Apply chart mode: 'total' | 'timbrage' | 'magasinage' | 'agent' | 'surestarie' | 'detail'
  function applyCAMode(mode){
    const sel = mode || (document.getElementById('ca-mode-select') && document.getElementById('ca-mode-select').value) || 'total';
    let newDatasets = [];
    if(sel === 'detail'){
      // stacked view with activities
      barChart.options.scales.x.stacked = true;
      barChart.options.scales.y.stacked = true;
      const agentSeries = (datasets.agent_currencies && datasets.agent_currencies.length)? datasets.agent_currencies : [datasets.agent];
      newDatasets = [
        Object.assign({type:'bar', stack:'s1', borderWidth:1}, datasets.timbrage),
        Object.assign({type:'bar', stack:'s1', borderWidth:1}, datasets.magasinage),
        ...agentSeries.map(s=>Object.assign({type:'bar', stack:'s1', borderWidth:1}, s)),
        Object.assign({type:'bar', stack:'s1', borderWidth:1}, datasets.surestarie)
      ];
    }else{
      barChart.options.scales.x.stacked = false;
      barChart.options.scales.y.stacked = false;
      if(sel === 'agent' && datasets.agent_currencies && datasets.agent_currencies.length){
        newDatasets = datasets.agent_currencies.map(s=> Object.assign({type:'bar', borderWidth:1}, s));
      } else {
        const entry = datasets[sel] || datasets.total;
        newDatasets = [Object.assign({type:'bar', borderWidth:1}, entry)];
      }
    }
    barChart.data.datasets = newDatasets;
    barChart.update();
  }

  const caSelectElem = document.getElementById('ca-mode-select');
  if(caSelectElem){
    caSelectElem.addEventListener('change', function(){ applyCAMode(this.value); });
  }

  // reuse `urlParams` declared earlier in this DOMContentLoaded scope
  const listParam=urlParams.get('list');
  const listOnlyParam=urlParams.get('listOnly');
  const chartParam=urlParams.get('chart');
  const deviseParam=urlParams.get('devise');
  const commercialParam=urlParams.get('commercial');
  const typeParam=urlParams.get('type');
  // Normalize legacy/variant list param values so new KPI keys reuse the
  // invoices list behavior. If URL contains 'invoices-agent' or
  // 'invoices-surestarie', treat it as 'invoices' and set the matching type.
  let normalizedListParam = listParam;
  let normalizedTypeParam = typeParam;
  if(listParam === 'invoices-agent'){
    normalizedListParam = 'invoices';
    if(!normalizedTypeParam) normalizedTypeParam = 'A';
  } else if(listParam === 'invoices-surestarie'){
    normalizedListParam = 'invoices';
    if(!normalizedTypeParam) normalizedTypeParam = 'S';
  } else if(listParam === 'invoices-magasinage'){
    normalizedListParam = 'invoices';
    if(!normalizedTypeParam) normalizedTypeParam = 'M';
  }
  const listMonthParam = urlParams.get('list_month');
  const listYearParam = urlParams.get('list_year');
  if(listOnlyParam){
    document.body.classList.add('list-only');
  }
  if(listOnlyParam&&normalizedListParam){
    const activeCard=document.querySelector(`.kpi-card[data-key="${listParam}"]`);
    if(activeCard) activeCard.classList.add('active');
    const opts={};
    if(listMonthParam) opts.month=Number(listMonthParam);
    if(listYearParam) opts.year=Number(listYearParam);
    if(normalizedTypeParam) opts.type = normalizedTypeParam;
    if(normalizedListParam==='generated'&&commercialParam){
      showFreightByCommercial(commercialParam);
    }else if(normalizedListParam==='generated'&&deviseParam){
      showFreightByDevise(deviseParam);
    }else{
      renderList(normalizedListParam, opts);
    }
  }else if(chartParam==='devise'){
    document.body.classList.add('chart-only');
    loadDeviseChart();
  }

  initKpiCounts();

  if(listSearch){
    listSearch.addEventListener('input',function(){
      if(!currentListKey) return;
      currentPage=1;
      applySearchFilter();
    });
  }

  if(listPageSize){
    listPageSize.addEventListener('change',function(){
      if(!currentListKey) return;
      currentPage=1;
      applySearchFilter();
    });
  }

  if(listPagePrev){
    listPagePrev.addEventListener('click',function(){
      if(currentPage>1){
        currentPage-=1;
        applySearchFilter();
      }
    });
  }

  if(listPageNext){
    listPageNext.addEventListener('click',function(){
      currentPage+=1;
      applySearchFilter();
    });
  }

  if(listBack){
    listBack.addEventListener('click',function(){
      if(currentListKey!=='generated') return;
      listMode='summary';
      commercialFilter=null;
      listTitle.textContent=listData.generated.title;
      listBack.style.display='none';
      currentColumns=columnSets.freightSummary;
      renderColumns(currentColumns);
      const grouped=new Map();
      listCache.freight.forEach(item=>{
        const commercial=item.email_utilisateur||item.id_utilisateur||'Non assigné';
        if(!grouped.has(commercial)){
          grouped.set(commercial,{
            commercial,
            count:0,
            total_achat:0,
            total_vente:0,
            total_marge:0
          });
        }
        const row=grouped.get(commercial);
        row.count+=1;
        const achat=Number(item.mont_achat)||0;
        const vente=Number(item.mont_vente)||0;
        row.total_achat+=achat;
        row.total_vente+=vente;
        row.total_marge+=(vente-achat);
      });
      currentItems=Array.from(grouped.values());
      currentPage=1;
      applySearchFilter();
    });
  }

  if(columnToggleBtn&&columnMenu){
    columnToggleBtn.addEventListener('click',function(){
      columnMenu.classList.toggle('visible');
    });
    document.addEventListener('click',function(e){
      if(!e.target.closest('.column-toggle')){
        columnMenu.classList.remove('visible');
      }
    });
  }

  const barCtx=document.getElementById('barChart').getContext('2d');
  const barLabels=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc'];
  const barData=new Array(12).fill(0);
  // datasets: total + activities
  const datasets = {
    timbrage: { label: 'Timbrage', data: [...barData], backgroundColor: '#3498db' },
    total: { label: 'Total (TND)', data: [...barData], backgroundColor: 'rgba(52,152,219,0.6)', borderColor: '#3498db' },
    magasinage: { label: 'Magasinage', data: [...barData], backgroundColor: '#2ecc71' },
    agent: { label: 'Agent', data: [...barData], backgroundColor: '#f39c12' },
    surestarie: { label: 'Surestarie', data: [...barData], backgroundColor: '#e74c3c' }
  };

  // Note: use global `window.monthlyActivityCache` populated earlier

  const barChart=new Chart(barCtx,{
    type:'bar',
    data:{
      labels:barLabels,
      datasets:[
        // default show total
        Object.assign({type:'bar', borderWidth:1}, datasets.total)
      ]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      onClick:function(evt,elements){
        if(!elements.length) return;
        // Only open invoice list when mode is 'total' or 'detail'
        const mode = document.getElementById('ca-mode-select')?.value || 'total';
        if(mode !== 'total' && mode !== 'detail') return;
        const el = elements[0];
        const monthIndex = el.index; // 0-based index into labels
        const month = monthIndex + 1; // 1-based month
        const now = new Date();
        const year = now.getFullYear(); // only current year

        // determine which dataset was clicked to infer invoice type/currency
        let typeChar = null;
        let currency = null;
        try{
          const dsIndex = el.datasetIndex;
          const ds = this.data && this.data.datasets && this.data.datasets[dsIndex] ? this.data.datasets[dsIndex] : {};
          const lbl = (ds.label||'').toString();
          if(/\bTimbrage\b/i.test(lbl)) typeChar = 'T';
          else if(/\bMagasinage\b/i.test(lbl)) typeChar = 'M';
          else if(/\bSurestarie\b/i.test(lbl)) typeChar = 'S';
          else if(/\bAgent\b/i.test(lbl)) typeChar = 'A';
          // extract currency for agent series like 'Agent - EUR'
          const m = lbl.match(/Agent\s*[-:]?\s*(\w{3})/i);
          if(m && m[1]) currency = m[1].toUpperCase();
        }catch(e){ /* ignore */ }

        const url = new URL(window.location.href);
        url.searchParams.set('list','invoices');
        url.searchParams.set('listOnly','1');
        url.searchParams.set('list_month',String(month));
        url.searchParams.set('list_year',String(year));
        if(typeChar) url.searchParams.set('type', typeChar);
        if(currency) url.searchParams.set('currency', currency);
        window.open(url.toString(),'_blank');

        const opts = { month, year };
        if(typeChar) opts.type = typeChar;
        if(currency) opts.currency = currency;
        renderList('invoices', opts);
        if(listSearch) listSearch.value='';
      },
      scales:{
        y:{
          beginAtZero:true,
          grid:{color:'rgba(0,0,0,0.05)'},
          stacked:false
        },
        x:{grid:{color:'rgba(0,0,0,0.05)'}, stacked:false}
      },
      plugins:{
        legend:{display:true},
        tooltip:{
          callbacks:{
            label:function(context){
              const val = (context.parsed && (context.parsed.y !== undefined ? context.parsed.y : context.parsed)) || 0;
              // Determine currency suffix from dataset if possible (Agent may be EUR/USD)
              const ds = context.dataset || {};
              const lbl = (ds.label || '').toString();
              let suffix = 'TND';
              try{
                if(/\bEUR\b/i.test(lbl)) suffix = 'EUR';
                else if(/\bUSD\b/i.test(lbl)) suffix = 'USD';
                else if(/\bTND\b/i.test(lbl)) suffix = 'TND';
              }catch(e){ /* ignore */ }
              try{ return `${formatAmount(val)} ${suffix}`; }catch(e){ return `${val} ${suffix}`; }
            }
          }
        }
      }
    }
  });

  async function loadMonthlyTurnover(){
    try{
      const curYear = new Date().getFullYear();
      const resp = await fetch(`/api/factures/annual-summary?year=${curYear}`);
      const data = await resp.json();
      if(!resp.ok) throw new Error(data.error || 'Erreur API annual-summary');

      const rows = data.rows || [];
      const timbrage = new Array(12).fill(0);
      const magasinage = new Array(12).fill(0);
      const surestarie = new Array(12).fill(0);
      const agent_by_currency = {}; // currency -> array[12]
      const annual_totals = {}; // type -> { cur -> total }

      rows.forEach(r=>{
        const type = (r.type_facture||'').toString().trim();
        const mois = Number(r.mois||0);
        const devise = (r.devise||'TND').toString();
        const total = Number(r.total||0);
        if(mois === 0){
          if(!annual_totals[type]) annual_totals[type] = {};
          annual_totals[type][devise] = (annual_totals[type][devise]||0) + total;
        } else {
          if(type === 'A'){
            if(!agent_by_currency[devise]) agent_by_currency[devise] = new Array(12).fill(0);
            agent_by_currency[devise][mois-1] += total;
          } else if(type === 'T'){
            timbrage[mois-1] += total;
          } else if(type === 'M'){
            magasinage[mois-1] += total;
          } else if(type === 'S'){
            surestarie[mois-1] += total;
          }
        }
      });

      datasets.timbrage.data = timbrage;
      datasets.magasinage.data = magasinage;
      datasets.surestarie.data = surestarie;

      // Build agent currency datasets
      datasets.agent_currencies = [];
      const paletteLocal = ['#f39c12','#9b59b6','#1abc9c','#e67e22','#3498db','#2ecc71','#34495e'];
      let pi = 0;
      Object.keys(agent_by_currency).forEach(cur=>{
        datasets.agent_currencies.push({
          label: `Agent - ${cur}`,
          data: agent_by_currency[cur].slice(0,12),
          backgroundColor: paletteLocal[(pi++)%paletteLocal.length]
        });
      });

      // compute current-month totals for KPI cards (use monthly series, not annual)
      const sum = arr => Array.isArray(arr)? arr.reduce((a,b)=>a+Number(b||0),0):0;
      const curMonthIndex = new Date().getMonth(); // 0-based
      const magCurrent = Number(magasinage[curMonthIndex]||0);
      const surCurrent = Number(surestarie[curMonthIndex]||0);
      const timbrageCurrent = Number(timbrage[curMonthIndex]||0);

      // Agent totals per currency for current month
      const agentTotals = {};
      if(Object.keys(agent_by_currency).length){
        Object.keys(agent_by_currency).forEach(cur=>{ agentTotals[cur] = Number(agent_by_currency[cur][curMonthIndex]||0); });
      } else if(annual_totals['A']){
        // fallback: if only annual totals available, approximate by dividing by 12
        Object.entries(annual_totals['A']).forEach(([cur,v])=>{ agentTotals[cur]=Number((v||0)/12); });
      }

      // update KPI DOM with current month values
      setKpiValue('invoices-magasinage', formatAmount(magCurrent) + ' TND');
      setKpiValue('invoices-magasinage-tht-month', formatAmount(magCurrent) + ' TND');
      setKpiValue('invoices-magasinage-tht-year', formatAmount(magCurrent) + ' TND');

      setKpiValue('invoices-surestarie', formatAmount(surCurrent) + ' TND');
      setKpiValue('invoices-surestarie-tht-month', formatAmount(surCurrent) + ' TND');
      setKpiValue('invoices-surestarie-tht-year', formatAmount(surCurrent) + ' TND');

      // set Timbrage invoice KPI (main invoices card) to current month timbrage
      setKpiValue('invoices', formatAmount(timbrageCurrent) + ' TND');

      // agent small KPI elements (EUR/USD) if present — show current month
      const eurEl = document.querySelector('[data-kpi-value="agent-eur"]');
      const usdEl = document.querySelector('[data-kpi-value="agent-usd"]');
      if(eurEl) eurEl.textContent = formatAmount(agentTotals['EUR']||0) + ' EUR';
      if(usdEl) usdEl.textContent = formatAmount(agentTotals['USD']||0) + ' USD';

      // compute totals dataset (sum of TND categories only)
      const totals = new Array(12).fill(0);
      for(let i=0;i<12;i++){
        totals[i] = Number(timbrage[i]||0) + Number(magasinage[i]||0) + Number(surestarie[i]||0);
      }
      datasets.total.data = totals;

      applyCAMode(document.getElementById('ca-mode-select')?.value || 'total');
    }catch(e){
      console.error('Erreur chargement CA mensuel:', e);
    }
  }

  // trigger the (now-stubbed) loader to initialize empty chart state
  loadMonthlyTurnover();

  // Invoices modal logic
  const invoicesModal = document.getElementById('invoices-modal');
  const invoicesModalBody = document.getElementById('invoices-modal-body');
  const invoicesModalTitle = document.getElementById('invoices-modal-title');
  const invoicesModalClose = document.getElementById('invoices-modal-close');

  function closeInvoicesModal(){
    if(!invoicesModal) return;
    invoicesModal.classList.remove('visible');
    invoicesModal.setAttribute('aria-hidden','true');
    invoicesModalBody.innerHTML='';
  }

  function openInvoicesModal(){
    if(!invoicesModal) return;
    invoicesModal.classList.add('visible');
    invoicesModal.setAttribute('aria-hidden','false');
  }

  // Handle clicks on invoice reference links inside lists
  document.addEventListener('click', async function(e){
    const a = e.target.closest && e.target.closest('.invoice-link');
    if(!a) return;
    e.preventDefault();
    const inv = a.getAttribute('data-invoice');
    if(!inv) return;
    try{
      // Exact UI fallback: take the same visible "Nom Commercial" from the clicked row.
      let clickedRowCommercial = '';
      try{
        const rowEl = a.closest('tr');
        const cell = rowEl && (rowEl.querySelector('td[data-col="nom_commercial"] .cell-content') || rowEl.querySelector('td[data-col="nom_commercial"]'));
        if(cell) clickedRowCommercial = String(cell.textContent || '').trim();
      }catch(err){ /* ignore */ }

      // Primary source for modal header: reuse the same row already visible in the list.
      let listHeaderCandidate = null;
      try{
        const invNorm = normalizeInvoiceRef(inv);
        listHeaderCandidate = invoiceHeaderMap.get(invNorm) || (currentItems || []).find(r => {
          const refs = [
            r && (r.reference ?? r.FF_H_NumFact ?? r.AA_H_Reference ?? r.AA_H_NumFacture),
            r && r.invoice_num
          ].filter(Boolean).map(x => normalizeInvoiceRef(x));
          return refs.includes(invNorm);
        }) || null;
        if(!listHeaderCandidate && clickedRowCommercial){
          listHeaderCandidate = { nom_commercial: clickedRowCommercial };
        } else if(listHeaderCandidate && clickedRowCommercial && (!listHeaderCandidate.nom_commercial || String(listHeaderCandidate.nom_commercial).trim()==='')){
          listHeaderCandidate.nom_commercial = clickedRowCommercial;
        }
      }catch(err){ /* ignore */ }

      // If link marked as AA, query AA details directly
      let rows = [];
      const isAA = a.getAttribute('data-aa');
      if(isAA){
        // Try to get entete/context from aa-detail listing for a better header
        let headerCandidate = listHeaderCandidate;
        try{
          const listResp = await fetch('/api/factures/aa-detail?limit=0');
          if(listResp.ok){
            const listJson = await listResp.json();
            const candidates = listJson.factures || [];
            headerCandidate = candidates.find(r => {
              const refs = [r.AA_H_Reference, r.reference, r.AA_H_NumFacture, r.AA_H_NumFact];
              return refs.some(x => x && String(x).trim() === String(inv).trim());
            }) || null;
          }
        }catch(e){ /* ignore */ }
        const resp2 = await fetch(`/api/factures/details-aa?reference=${encodeURIComponent(inv)}`);
        if(resp2.ok){
          const j2 = await resp2.json();
          rows = j2.details || [];
          if(headerCandidate){
            // attach header candidate to details array for modal header mapping
            try{ rows.__header = headerCandidate; }catch(e){ /* ignore */ }
          }
        }
      } else {
        // fetch FF detail rows and show in modal (reuse invoices modal table)
        const resp = await fetch(`/api/factures/details-by-invoices?invoices=${encodeURIComponent(inv)}`);
        let json = await resp.json();
        if(resp.ok){ rows = json.details || []; }
        // fallback to AA details if FF details empty
        if(!rows.length){
          try{
            const resp2 = await fetch(`/api/factures/details-aa?reference=${encodeURIComponent(inv)}`);
            const j2 = await resp2.json();
            if(resp2.ok){ rows = j2.details || []; }
          }catch(e){ /* ignore */ }
        }
        // Attach list row context when available so modal header can reuse list info.
        try{ if(listHeaderCandidate) rows.__header = listHeaderCandidate; }catch(e){ /* ignore */ }
      }
      invoicesModalTitle.textContent = `Détails — ${inv}`;
      const infoEl = document.getElementById('invoices-modal-info');
      if(!rows.length){
        if(infoEl) infoEl.textContent = '';
        invoicesModalBody.innerHTML = `<tr><td colspan="5">Aucun détail trouvé pour ${inv}</td></tr>`;
      } else {
        // Extract entête/context: prefer entête found from AA listing (rows.__header), else use first detail row
        const first = (rows && rows.__header) ? rows.__header : (listHeaderCandidate || rows[0] || {});
        const getVal = (obj, keys) => {
          for(const k of keys){
            if(obj && obj[k]!==undefined && obj[k]!==null && String(obj[k]).trim()!=='') return obj[k];
          }
          return '';
        };
        const dpRaw = getVal(first, ['date_process','AA_H_DateProcess','AA_D_DateProcess','AA_D_Date','AA_D_Date_Process']);
        const dp = dpRaw ? formatDateValue(dpRaw) : '';
        const dossier = getVal(first, ['dossier','AA_H_Dossier','AA_D_Dossier','AA_D_DossierRef','AA_H_DossierRef']);
        const client = getVal(first, ['nom_client','AA_H_NomClient','AA_D_NomClient','AA_H_NomClientFinal']);
        const commercial = getVal(first, ['nom_commercial','id_commercial','FF_H_IdCommercial','AA_H_IdCommercial','AA_H_NomCommercial','AA_D_NomCommercial','AA_H_NomCommercial']);
        // If header commercial is empty, try to find it in the detail rows as a fallback
        let commercialFallback = commercial;
        if(!commercialFallback || String(commercialFallback).trim()===''){
          for(const r of rows){
            const c = getVal(r, ['nom_commercial','id_commercial','FF_H_IdCommercial','AA_H_IdCommercial','AA_H_NomCommercial','AA_D_NomCommercial','AA_D_NomCommercial','AA_H_NomCommercial']);
            if(c && String(c).trim()!==''){
              commercialFallback = c;
              break;
            }
          }
        }
        // Page-level fallback: find a commercial from already loaded list rows
        // using the same dossier/house context.
        if(!commercialFallback || String(commercialFallback).trim()===''){
          try{
            const dossierNorm = String(dossier || '').trim().toUpperCase();
            const houseNorm = String(house || '').trim().toUpperCase();
            const rowsPool = Array.isArray(currentItems) ? currentItems : [];

            const pickCommercial = (row) => getVal(row, [
              'nom_commercial','id_commercial','FF_H_IdCommercial',
              'AA_H_IdCommercial','AA_H_NomCommercial','AA_D_NomCommercial'
            ]);

            // strict match: same dossier + same house
            for(const r of rowsPool){
              const d = String((r && (r.dossier || r.AA_H_Dossier)) || '').trim().toUpperCase();
              const h = String((r && (r.house || r.AA_H_House)) || '').trim().toUpperCase();
              if(dossierNorm && houseNorm && d === dossierNorm && h === houseNorm){
                const c = pickCommercial(r);
                if(c && String(c).trim()!==''){
                  commercialFallback = c;
                  break;
                }
              }
            }

            // relaxed match: same dossier only
            if((!commercialFallback || String(commercialFallback).trim()==='') && dossierNorm){
              for(const r of rowsPool){
                const d = String((r && (r.dossier || r.AA_H_Dossier)) || '').trim().toUpperCase();
                if(d === dossierNorm){
                  const c = pickCommercial(r);
                  if(c && String(c).trim()!==''){
                    commercialFallback = c;
                    break;
                  }
                }
              }
            }
          }catch(err){ /* ignore */ }
        }
        if((!commercialFallback || String(commercialFallback).trim()==='') && clickedRowCommercial){
          commercialFallback = clickedRowCommercial;
        }
        if(!commercialFallback || String(commercialFallback).trim()===''){
          commercialFallback = '-';
        }
        const eta = getVal(first, ['eta','AA_H_ETA','AA_D_ETA']);
        const house = getVal(first, ['house','AA_H_House','AA_D_House']);
        const service = getVal(first, ['service','AA_H_Service','AA_D_Service']);
        if(infoEl){
          infoEl.innerHTML = `
            <strong>Dossier:</strong> ${dossier} &nbsp; • &nbsp;
            <strong>Client:</strong> ${client} &nbsp; • &nbsp;
            <strong>Commercial:</strong> ${commercialFallback} &nbsp; • &nbsp;
            <strong>Date:</strong> ${dp} &nbsp; • &nbsp;
            <strong>ETA:</strong> ${eta} &nbsp; • &nbsp;
            <strong>House:</strong> ${house} &nbsp; • &nbsp;
            <strong>Service:</strong> ${service}
          `;
        }
        // Render detail rows (map various possible column names from FF or AA views)
        invoicesModalBody.innerHTML = rows.map(r=>{
          const lib = r.libelle || r.FF_D_Libelle || r.AA_D_Libelle || r.AA_D_Intitule || r.description || r.Libelle || '';
          const devise = r.devise || r.FF_D_Devise || r.AA_D_Devise || r.currency || 'TND';
          const montant = (r.montant!==undefined? r.montant : (r.FF_D_Montant!==undefined? r.FF_D_Montant : (r.AA_D_Montant!==undefined? r.AA_D_Montant : '')));
          const montant_tva = (r.montant_tva!==undefined? r.montant_tva : (r.FF_D_MontantTVA!==undefined? r.FF_D_MontantTVA : (r.AA_D_MontantTVA!==undefined? r.AA_D_MontantTVA : '')));
          const montant_ttc = (r.montant_ttc!==undefined? r.montant_ttc : (r.FF_D_MontantTTC!==undefined? r.FF_D_MontantTTC : (r.AA_D_MontantTTC!==undefined? r.AA_D_MontantTTC : '')));
          const montant_ht_tnd = (r.montant_ht_tnd!==undefined? r.montant_ht_tnd : (r.FF_D_MontantHT_TND!==undefined? r.FF_D_MontantHT_TND : (r.AA_D_MontantHT_TND!==undefined? r.AA_D_MontantHT_TND : '')));
          return `<tr>
            <td>${lib}</td>
            <td>${devise}</td>
            <td>${montant!==''? (Number(montant)||montant===0? formatAmount(montant):montant) : ''}</td>
            <td>${montant_tva!==''? (Number(montant_tva)||montant_tva===0? formatAmount(montant_tva):montant_tva) : ''}</td>
            <td>${montant_ttc!==''? (Number(montant_ttc)||montant_ttc===0? formatAmount(montant_ttc):montant_ttc) : ''}</td>
            <td>${montant_ht_tnd!==''? (Number(montant_ht_tnd)||montant_ht_tnd===0? formatAmount(montant_ht_tnd):montant_ht_tnd) : ''}</td>
          </tr>`;
        }).join('');
      }
      openInvoicesModal();
    }catch(err){
      console.error('Erreur fetch invoice details', err);
      alert('Erreur chargement détails facture');
    }
  });

  invoicesModalClose?.addEventListener('click', closeInvoicesModal);
  invoicesModal?.addEventListener('click', function(e){ if(e.target===invoicesModal) closeInvoicesModal(); });
  document.addEventListener('keydown', function(e){ if(e.key==='Escape') closeInvoicesModal(); });

  async function showInvoicesModal(month, year){
    try{
      invoicesModalTitle.textContent = `Factures — ${month}/${year}`;
      // reuse fetchInvoices (calls /api/factures/aa-detail)
      const all = await fetchInvoices();
      const filtered = (all||[]).filter(it=>{
        if(!it.date_process) return false;
        const d=new Date(it.date_process);
        if(Number.isNaN(d.getTime())) return false;
        return d.getFullYear()===Number(year) && (d.getMonth()+1)===Number(month);
      });
      if(!filtered.length){
        invoicesModalBody.innerHTML = `<tr><td colspan="8">Aucune facture trouvée pour ${month}/${year}</td></tr>`;
      }else{
        invoicesModalBody.innerHTML = filtered.map(row=>{
          return `<tr>
            <td>${row.AA_H_Reference||row.reference||row.reference}</td>
            <td>${formatDateValue(row.AA_H_DateProcess||row.date_process)}</td>
            <td>${row.AA_H_Dossier||row.dossier||''}</td>
            <td>${row.AA_H_NomClient||row.nom_client||''}</td>
            <td>${row.AA_H_ETA||row.eta||''}</td>
            <td>${row.AA_H_House||row.house||''}</td>
            <td>${row.AA_H_Service||row.service||''}</td>
            <td>${(row.total_ttc!==undefined?formatAmount(row.total_ttc): (row.FF_T_TotalTTC?formatAmount(row.FF_T_TotalTTC):'0'))} TND</td>
          </tr>`;
        }).join('');
      }
      openInvoicesModal();
    }catch(err){
      invoicesModalBody.innerHTML = `<tr><td colspan="8">Erreur: ${err.message}</td></tr>`;
      openInvoicesModal();
    }
  }

  const activityCtx=document.getElementById('activityChart').getContext('2d');
  const activityChart=new Chart(activityCtx,{
    type:'pie',
    data:{
      labels:['Timbrage','Magasinage','Surestarie','Agent (converti)'],
      datasets:[{
        data:[35,25,20,20],
        backgroundColor:['#3498db','#2ecc71','#e74c3c','#f39c12'],
        borderWidth:2,
        borderColor:'#fff'
      }]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      plugins:{
        legend:{display:false},
        tooltip:{
            callbacks:{
              label:function(context){
                const data=context.dataset.data||[];
                const value=Number(context.parsed)||0;
                try{
                  return `${context.label} ${formatAmount(value)} TND`;
                }catch(e){
                  return `${context.label} ${value} TND`;
                }
              }
            }
        }
      }
    }
  });

  async function loadActivityData(){
    try{
      // Prefer using the same monthly datasets as the histogram so values match exactly.
      // If the monthly datasets aren't loaded yet, load them first.
      if(!window.monthlyActivityCache || !datasets || !Array.isArray(datasets.timbrage.data) || datasets.timbrage.data.length===0){
        await loadMonthlyTurnover();
      }

      // Build annual totals from the monthly datasets (sums across months)
      const map = {};
      let agentTotal = 0;
      // Timbrage/Magasinage/Surestarie come from datasets.timbrage/magasinage/surestarie
      const sumArray = arr => (Array.isArray(arr)? arr.reduce((a,b)=>a+Number(b||0),0):0);
      map['Timbrage'] = sumArray(datasets.timbrage.data);
      map['Magasinage'] = sumArray(datasets.magasinage.data);
      map['Surestarie'] = sumArray(datasets.surestarie.data);

      // Agent per-currency datasets were built as datasets.agent_currencies
      if(Array.isArray(datasets.agent_currencies)){
        datasets.agent_currencies.forEach(ds=>{
          const label = (ds.label||'Agent').toString();
          const total = sumArray(ds.data);
          // Keep label starting with 'A' to be compatible with existing rendering
          const key = label.startsWith('A')? label : ('Agent - ' + label.split('-').pop().trim());
          map[key] = (map[key]||0) + total;
          agentTotal += total;
        });
      }

      const tTimbrage = Number(map['Timbrage']||0);
      const tMagasinage = Number(map['Magasinage']||0);
      const tSurestarie = Number(map['Surestarie']||0);
      // compute totals by currency from the aggregated `map` keys
      const totalsByCurrency = {};
      Object.keys(map).forEach(raw=>{
        if(!raw) return;
        const parts = raw.split('-').map(s=>s.trim());
        const amount = Number(map[raw]||0);
        if(parts.length>1){
          const cur = parts[1].toUpperCase();
          totalsByCurrency[cur] = (totalsByCurrency[cur]||0) + amount;
        } else {
          totalsByCurrency['TND'] = (totalsByCurrency['TND']||0) + amount;
        }
      });

      document.querySelector('[data-activity-value="timbrage"]').textContent = formatAmount(tTimbrage) + ' TND';
      document.querySelector('[data-activity-value="magasinage"]').textContent = formatAmount(tMagasinage) + ' TND';
      document.querySelector('[data-activity-value="agent"]').textContent = formatAmount(agentTotal) + ' TND';
      document.querySelector('[data-activity-value="surestarie"]').textContent = formatAmount(tSurestarie) + ' TND';
      // overall total row removed per request; currency totals shown below

      // Build labels: keep order Timbrage, Magasinage, then Agent currencies, then Surestarie
      const agentLabels = Object.keys(map).filter(k=>k && k[0].toUpperCase()==='A').sort();
      const labels = ['Timbrage','Magasinage', ...agentLabels, 'Surestarie'].filter((v,i,a)=>a.indexOf(v)===i);
      const dataVals = labels.map(l=> Number(map[l]||0));
      const palette = ['#3498db','#2ecc71','#f39c12','#e74c3c','#9b59b6','#1abc9c','#34495e','#e67e22'];
      const bg = labels.map((lbl,i)=> {
        if(String(lbl).trim().toLowerCase() === 'surestarie') return '#e74c3c';
        return palette[i%palette.length];
      });
      activityChart.data.labels = labels;
      activityChart.data.datasets[0].data = dataVals;
      activityChart.data.datasets[0].backgroundColor = bg;
      // update currency totals UI (TND only)
      const tndEl = document.getElementById('activity-total-tnd');
      if(tndEl) tndEl.textContent = formatAmount(totalsByCurrency['TND']||0) + ' TND';

      // render agent per-currency rows in the activity list
      const agentContainer = document.getElementById('activity-agent-container');
      if(agentContainer){
        // clear except keep a fallback total element if present
        agentContainer.innerHTML = '';
        const sortedAgentKeys = agentLabels.slice().sort();
        if(sortedAgentKeys.length===0){
          // show aggregated agent KPI fallback
          const span = document.createElement('span');
          span.textContent = formatAmount(agentTotal) + ' TND';
          agentContainer.appendChild(span);
        } else {
          sortedAgentKeys.forEach(k=>{
            const val = Number(map[k]||0);
            const row = document.createElement('div');
            row.style.display='flex';
            row.style.justifyContent='space-between';
            row.style.gap='8px';
            row.style.marginTop='4px';
            const left = document.createElement('div');
            left.textContent = k.replace(/^A\s*-\s*/i,'Agent - ');
            const right = document.createElement('div');
            // decide currency suffix from label
            const parts = k.split('-').map(s=>s.trim());
            const cur = parts.length>1?parts[1].toUpperCase():'TND';
            right.textContent = formatAmount(val) + ' ' + (cur==='USD'?'USD':(cur==='EUR'?'EUR':'TND'));
            row.appendChild(left);
            row.appendChild(right);
            agentContainer.appendChild(row);
          });
        }
      }
      activityChart.update();
    }catch(err){
      console.error('Erreur chargement activité:',err);
    }
  }

  function renderDeviseChart(labels,values){
    // New multi-dataset renderer (labels = months, values = datasets array)
    if(!deviseChartCanvas) return;
    const ctx=deviseChartCanvas.getContext('2d');
    const config={
      type:'bar',
      data:{ labels, datasets: values },
      options:{
        responsive:true,
        maintainAspectRatio:false,
        plugins:{ legend:{ display:true, position:'top' } },
        layout:{ padding:{ left:12, right:12, top:6, bottom:6 } },
        scales:{
          y:{ beginAtZero:true, grid:{ color:'rgba(0,0,0,0.05)' } },
          x:{ grid:{ color:'rgba(0,0,0,0.05)' }, offset:true, ticks:{ autoSkip:false, maxRotation:0, minRotation:0 } }
        },
        onClick:async function(evt,elements){
          if(!elements.length) return;
          const el=elements[0];
          const datasetIndex=el.datasetIndex;
          const monthIndex=(el.index!==undefined?el.index:(el.dataIndex!==undefined?el.dataIndex:el._index));
          const currency=this.data.datasets[datasetIndex].label;
          const yearSelect=document.getElementById('devise-year-select');
          const selYear=yearSelect?Number(yearSelect.value):new Date().getFullYear();
          if(!currency) return;
          try{
            const freightItems=await fetchFreightItems();
            const filtered=freightItems.filter(i=>{
              const d=i.date_creation||i.date_process||i.date||null;
              if(!d) return false;
              const dt=new Date(d);
              if(Number.isNaN(dt.getTime())) return false;
              if(dt.getFullYear()!==selYear) return false;
              if(dt.getMonth()!==monthIndex) return false;
              return (i.devise||'N/A')===currency;
            });
            renderDeviseCommercialSummary(filtered,currency,monthIndex,selYear);
            // If the page was opened with ?listOnly=1 we must NOT force-open the detailed list view
            const _urlParams = new URLSearchParams(window.location.search || '');
            if(_urlParams.get('listOnly')){
              return;
            }
            // also show detailed list for the selected currency/month/year
            listMode='detail';
            currentListKey='generated';
            if(listBack) listBack.style.display='inline-flex';
            const monthNames=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc'];
            listTitle.textContent=`Détails - ${currency} ${monthNames[monthIndex]||''} ${selYear}`;
            currentColumns=columnSets.freightCommercialDetails;
            renderColumns(currentColumns);
            currentItems=filtered.map(i=>({ ...i, marge:(Number(i.mont_vente)||0)-(Number(i.mont_achat)||0) }));
            currentPage=1;
            applySearchFilter();
            document.body.classList.add('chart-only','show-chart-list');
          }catch(err){
            console.error('Erreur filtrage par devise/mois:',err);
          }
        }
      }
    };
    if(!deviseChart){
      deviseChart=new Chart(ctx,config);
    }else{
      deviseChart.config.type=config.type;
      deviseChart.data.labels=config.data.labels;
      deviseChart.data.datasets=config.data.datasets;
      deviseChart.options=config.options;
      deviseChart.update();
    }
  }

  async function loadDeviseChart(year){
    try{
      const freightItems=await fetchFreightItems();
      // build available years
      const years=new Set();
      freightItems.forEach(i=>{
        const d=i.date_creation||i.date_process||i.date||null;
        if(d){
          const y=new Date(d).getFullYear();
          if(!Number.isNaN(y)) years.add(y);
        }
      });
      const yearSelect=document.getElementById('devise-year-select');
      if(yearSelect){
        const arr=Array.from(years).sort((a,b)=>b-a);
        if(!arr.length) arr.push(new Date().getFullYear());
        yearSelect.innerHTML=arr.map(y=>`<option value="${y}" ${y===(year||arr[0])?'selected':''}>${y}</option>`).join('');
        yearSelect.onchange=function(){ loadDeviseChart(parseInt(this.value,10)); };
      }
      const selYear=year||Number(yearSelect?.value)||new Date().getFullYear();
      const monthLabels=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc'];
      // aggregate per currency per month
      const map={};
      freightItems.forEach(i=>{
        const d=i.date_creation||i.date_process||i.date||null;
        if(!d) return;
        const dt=new Date(d);
        if(Number.isNaN(dt.getTime())) return;
        if(dt.getFullYear()!==selYear) return;
        const m=dt.getMonth();
        const cur=i.devise||'N/A';
        const achat=Number(i.mont_achat)||0;
        const vente=Number(i.mont_vente)||0;
        const marge=vente-achat;
        if(!map[cur]) map[cur]=new Array(12).fill(0);
        map[cur][m]+=marge;
      });
      const palette=['#3498db','#2ecc71','#e74c3c','#f39c12','#9b59b6','#1abc9c','#34495e'];
      const datasets=Object.keys(map).map((cur,i)=>({
        label:cur,
        data:map[cur].map(v=>Math.round(v)),
        backgroundColor:palette[i%palette.length]+'99',
        borderColor:palette[i%palette.length],
        borderWidth:1,
        barPercentage:0.6,
        categoryPercentage:0.8,
        maxBarThickness:80
      }));
      renderDeviseChart(monthLabels,datasets);
      renderDeviseCommercialSummary(freightItems);
      // Ensure details panel is hidden on initial chart load and summary tab active
      const detailsPanel=document.getElementById('devise-details');
      if(detailsPanel) detailsPanel.style.display='none';
      const tabSummary=document.getElementById('tab-summary');
      const tabDetails=document.getElementById('tab-details');
      if(tabSummary) tabSummary.classList.add('active');
      if(tabDetails) tabDetails.classList.remove('active');
      if(currencyContainer) currencyContainer.classList.add('visible');
    }catch(err){
      console.error('Erreur chargement devise:',err);
    }
  }

  async function showFreightByDevise(devise){
    try{
      if(listLoading) listLoading.classList.add('visible');
      const items=await fetchFreightItems();
      listMode='detail';
      currentListKey='generated';
      if(listBack) listBack.style.display='inline-flex';
      listTitle.textContent=`Détails - ${devise}`;
      currentColumns=columnSets.freightDetails;
      renderColumns(currentColumns);
      currentItems=items
        .filter(i=>(i.devise||'N/A')===devise)
        .map(i=>({
          ...i,
          marge:(Number(i.mont_vente)||0)-(Number(i.mont_achat)||0)
        }));
      currentPage=1;
      applySearchFilter();
      document.body.classList.add('chart-only','show-chart-list');
    }catch(err){
      listTableBody.innerHTML=`
        <tr>
          <td colspan="${(currentColumns||[]).length}">Erreur chargement:${err.message}</td>
        </tr>
      `;
    }finally{
      if(listLoading) listLoading.classList.remove('visible');
    }
  }

  async function showFreightByCommercial(commercial){
    try{
      if(listLoading) listLoading.classList.add('visible');
      const items=await fetchFreightItems();
      listMode='detail';
      currentListKey='generated';
      commercialFilter=commercial;
      if(listBack) listBack.style.display='inline-flex';
      listTitle.textContent=`Dossiers - ${commercial}`;
      currentColumns=columnSets.freightCommercialDetails;
      renderColumns(currentColumns);
      currentItems=items
        .filter(i=>(i.email_utilisateur||i.id_utilisateur||'Non assigné')===commercial)
        .map(i=>({
          ...i,
          marge:(Number(i.mont_vente)||0)-(Number(i.mont_achat)||0)
        }));
      currentPage=1;
      applySearchFilter();
    }catch(err){
      listTableBody.innerHTML=`
        <tr>
          <td colspan="${(currentColumns||[]).length}">Erreur chargement:${err.message}</td>
        </tr>
      `;
    }finally{
      if(listLoading) listLoading.classList.remove('visible');
    }
  }

  /* Generic client-side table sorter: attaches to tables with class `list-table` or `sortable` */
  function tryParseNumber(v){
    if(v===null||v===undefined) return null;
    let s = String(v);
    // normalize various unicode spaces (NBSP, narrow NBSP, thin space, etc.) to empty
    s = s.replace(/[\u00A0\u202F\u2009\u2007\u2008]/g, '');
    // remove any characters except digits, comma, dot, minus
    s = s.replace(/[^0-9,\.\-]/g,'');
    if(s.length===0) return null;
    // If both comma and dot are present, assume comma is thousand separator -> remove commas
    if(s.indexOf(',')!==-1 && s.indexOf('.')!==-1){
      s = s.replace(/,/g,'');
    } else {
      // otherwise, treat comma as decimal separator
      s = s.replace(/,/g,'.');
    }
    const n = parseFloat(s);
    return Number.isFinite(n)?n:null;
  }

  function sortTableRows(table, colIndex, asc){
    const tbody=table.tBodies[0];
    if(!tbody) return;
    const rows=Array.from(tbody.querySelectorAll('tr'));
    rows.sort((a,b)=>{
      const aCell=a.children[colIndex];
      const bCell=b.children[colIndex];
      const aText=(aCell? aCell.textContent.trim() : '');
      const bText=(bCell? bCell.textContent.trim() : '');
      // Detect date patterns like dd/mm/yyyy or dd-mm-yyyy or yyyy-mm-dd
      const dateRegex1 = /^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})$/; // dd/mm/yyyy
      const dateRegex2 = /^(\d{4})[\-](\d{1,2})[\-](\d{1,2})$/; // yyyy-mm-dd
      const aDateMatch1 = aText.match(dateRegex1);
      const bDateMatch1 = bText.match(dateRegex1);
      const aDateMatch2 = aText.match(dateRegex2);
      const bDateMatch2 = bText.match(dateRegex2);
      if((aDateMatch1 && bDateMatch1) || (aDateMatch2 && bDateMatch2)){
        function toDate(text, m1, m2){
          const d1 = text.match(dateRegex1);
          if(d1){
            const day = Number(d1[1]);
            const month = Number(d1[2]) - 1;
            let year = Number(d1[3]);
            if(year<100) year += 2000;
            return new Date(year, month, day);
          }
          const d2 = text.match(dateRegex2);
          if(d2){
            const year = Number(d2[1]);
            const month = Number(d2[2]) - 1;
            const day = Number(d2[3]);
            return new Date(year, month, day);
          }
          return null;
        }
        const aDt = toDate(aText);
        const bDt = toDate(bText);
        if(aDt && bDt){
          return asc? (aDt - bDt) : (bDt - aDt);
        }
      }
      const aNum=tryParseNumber(aText);
      const bNum=tryParseNumber(bText);
      if(aNum!==null && bNum!==null){
        return asc? aNum-bNum : bNum-aNum;
      }
      // fallback to localized string compare
      return asc? aText.localeCompare(bText,'fr') : bText.localeCompare(aText,'fr');
    });
    // re-append rows
    rows.forEach(r=>tbody.appendChild(r));
  }

  function attachSortableHeaders(table){
    if(!table || table._sortableAttached) return;
    const thead=table.tHead;
    if(!thead) return;
    const headers=Array.from(thead.querySelectorAll('th'));
    headers.forEach((th,idx)=>{
      th.classList.add('sortable');
      th.style.userSelect='none';
      th.addEventListener('click',function(){
        // toggle sort
        const isAsc=this.classList.toggle('sort-asc');
        this.classList.toggle('sort-desc',!isAsc);
        // clear other headers
        headers.forEach(h=>{ if(h!==this){ h.classList.remove('sort-asc','sort-desc'); } });
        sortTableRows(table, idx, isAsc);
      });
    });
    table._sortableAttached=true;
  }

  function makeTablesSortable(){
    const tables=document.querySelectorAll('table.list-table, table.sortable, table.devise-commercial-table');
    tables.forEach(t=>attachSortableHeaders(t));
    // observe for dynamic changes (e.g., renderColumns replaces thead)
    const observer=new MutationObserver(muts=>{
      muts.forEach(m=>{
        m.addedNodes && m.addedNodes.forEach(node=>{
          if(node.nodeType===1 && node.matches && node.matches('table.list-table, table.sortable')){
            attachSortableHeaders(node);
          }
          if(node.querySelectorAll){
            node.querySelectorAll && node.querySelectorAll('table.list-table, table.sortable').forEach(t=>attachSortableHeaders(t));
          }
        });
      });
    });
    observer.observe(document.body,{childList:true,subtree:true});
  }

  loadActivityData();
  
  // Cacher le chargement après 5 secondes maximum (sécurité)
 setTimeout(hideLoading, 5000);
});
