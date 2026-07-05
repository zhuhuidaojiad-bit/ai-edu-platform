/* ═══════════════════════════════════════════
   AI 智慧学伴 — 快乐学习引擎 v2.0 🎮✨
   新增：错题本持久化、真实AI聊天、学习报告增强、预科年级
   ═══════════════════════════════════════════ */

var G={grade:'初中',subj:'math',type:'all',qs:[],idx:0,done:false,panel:null,lastAnswer:'',streak:0,xp:0,streakHit:0,username:'',difficulty:0};
function el(id){return document.getElementById(id)}

// ═══════════════════════════════════════════
// MULTI-USER SYSTEM
// ═══════════════════════════════════════════
function userKey(k){return G.username?G.username+'_'+k:k}
function getUsers(){try{return JSON.parse(localStorage.getItem('learn_users')||'[]')}catch(e){return[]}}
function saveUsers(users){localStorage.setItem('learn_users',JSON.stringify(users))}

// 新用户采访状态
var onboardStep = 1;
var onboardData = {grade:'初中',weakSubjects:[],difficulty:3};

function showLoginModal(){
  var m=el('loginModal');if(!m)return;
  m.classList.remove('hidden');
  el('loginCard').classList.remove('hidden');
  el('onboardCard').classList.add('hidden');
  el('loginInput').value='';
  el('loginInput').focus();
  // 渲染已有用户列表
  var users=getUsers();
  var list=el('loginUserList');
  if(list)list.innerHTML=users.map(function(u){
    return '<span class="modal-user-chip" onclick="quickLogin(\''+u+'\')">👤 '+u+'</span>';
  }).join('');
  onboardStep=1;onboardData={grade:'初中',weakSubjects:[],difficulty:3};
  updateOnboardUI();
}

function quickLogin(name){
  el('loginInput').value=name;
  doLogin();
}

function doLogin(){
  var name=el('loginInput').value.trim();
  var code=el('accessCodeInput').value.trim();
  var errEl=el('loginError');
  if(!name||name.length<1){el('loginInput').focus();return}
  if(!code||code.length<2){el('accessCodeInput').focus();errEl.textContent='请输入访问码';return}
  errEl.textContent='正在验证...';

  // 调用后端API验证访问码
  fetch('/api/validate_code',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({code:code,nickname:name})
  })
  .then(function(r){return r.json()})
  .then(function(data){
    if(data.success){
      G.username=name;
      G.sessionToken=data.session_token;
      G.sessionExpires=data.expires_at;
      G.totalSeconds=data.total_remaining_seconds;
      localStorage.setItem(userKey('session_token'),data.session_token);
      localStorage.setItem(userKey('session_expires'),data.expires_at);
      toast('✅ '+data.message);

      var users=getUsers();
      if(users.indexOf(name)===-1){users.push(name);saveUsers(users)}

      // 显示欢迎语
      showWelcome(data);
    } else {
      errEl.textContent='❌ '+data.error;
    }
  })
  .catch(function(e){
    errEl.textContent='❌ 网络错误，请检查网络连接';
    console.warn('API error:',e);
  });
}

function showWelcome(data){
  el('loginCard').classList.add('hidden');
  el('onboardCard').classList.add('hidden');
  el('welcomeCard').classList.remove('hidden');

  var now=new Date();
  var hour=now.getHours();
  var greeting=hour<6?'夜深了':hour<9?'早上好':hour<12?'上午好':hour<14?'中午好':hour<18?'下午好':'晚上好';

  // 高考倒计时
  var gaokao=new Date(2027,5,7);
  var daysLeft=Math.ceil((gaokao-now)/(1000*60*60*24));

  el('welcomeTitle').textContent=greeting+'，'+data.nickname+'！';
  el('welcomeMsg').innerHTML='<span class="wm-name">'+data.nickname+'</span>，欢迎回来！<br>📅 今天是 '+now.getFullYear()+'年'+(now.getMonth()+1)+'月'+now.getDate()+'日<br>⏳ 距2027年高考还有 <span class="wm-days">'+daysLeft+'</span> 天<br>⏱ 本次学习时间：<b>'+data.duration_minutes+'分钟</b>';

  var expiresAt=new Date(data.expires_at);
  el('countdownMsg').innerHTML='🕐 学习时间截止：<b>'+expiresAt.getHours().toString().padStart(2,'0')+':'+expiresAt.getMinutes().toString().padStart(2,'0')+'</b>';

  startTimer(data.total_remaining_seconds);
}

function enterAppAfterWelcome(){
  el('loginModal').classList.add('hidden');
  var profile=localStorage.getItem(userKey('profile'));
  if(profile){
    try{
      var p=JSON.parse(profile);
      G.grade=p.grade||'初中';G.subj=p.weakSubjects?p.weakSubjects[0]||'math':'math';
      G.difficulty=p.difficulty||0;
    }catch(e){}
    enterApp();
  } else {
    el('welcomeCard').classList.add('hidden');
    el('onboardCard').classList.remove('hidden');
    onboardStep=1;updateOnboardUI();
  }
}

// ═══════════════════════
// TIMER
// ═══════════════════════
var timerInterval=null;
function startTimer(totalSeconds){
  G.totalSeconds=totalSeconds;
  updateTimerDisplay();
  if(timerInterval)clearInterval(timerInterval);
  timerInterval=setInterval(function(){
    G.totalSeconds--;
    if(G.totalSeconds<=0){
      G.totalSeconds=0;
      clearInterval(timerInterval);
      updateTimerDisplay();
      toast('⏰ 学习时间已用完，请重新输入访问码');
      setTimeout(function(){logout();},2000);
      return;
    }
    updateTimerDisplay();
    // 每30秒心跳一次
    if(G.totalSeconds%30===0&&G.sessionToken){
      fetch('/api/heartbeat',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({session_token:G.sessionToken})
      }).then(function(r){return r.json()}).then(function(d){
        if(!d.success||d.expired){clearInterval(timerInterval);toast('⏰ 会话已过期');setTimeout(function(){logout();},2000);}
      }).catch(function(){});
    }
  },1000);
  el('timerBadge').classList.remove('hidden');
}

function updateTimerDisplay(){
  var h=Math.floor(G.totalSeconds/3600);
  var m=Math.floor((G.totalSeconds%3600)/60);
  var s=G.totalSeconds%60;
  var display=(h>0?h+':':'')+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
  el('timerDisplay').textContent=display;
  var badge=el('timerBadge');
  if(G.totalSeconds<600)badge.classList.add('warning');
  else badge.classList.remove('warning');
}

function logout(){
  clearInterval(timerInterval);
  G.username='';G.sessionToken='';G.totalSeconds=0;
  el('timerBadge').classList.add('hidden');
  updateUserUI();
  showLoginModal();
}

function updateOnboardUI(){
  var c=el('onboardContent');if(!c)return;
  var dots=document.querySelectorAll('.os-dot');
  dots.forEach(function(d,i){
    d.classList.remove('active','done');
    if(i+1<onboardStep)d.classList.add('done');
    if(i+1===onboardStep)d.classList.add('active');
  });
  var lines=document.querySelectorAll('.os-line');
  lines.forEach(function(l,i){l.classList.toggle('done',i+1<onboardStep)});
  var back=el('onboardBack');if(back)back.style.display=onboardStep>1?'inline-flex':'none';
  var next=el('onboardNext');if(next)next.textContent=onboardStep===3?'🎉 开始学习':'下一步 ➡';

  if(onboardStep===1){
    var grades=[{g:'初中',icon:'🏫',sub:'中考真题 + 基础巩固'},{g:'高一',icon:'📗',sub:'新课标同步练习'},{g:'高二',icon:'📘',sub:'进阶提升训练'},{g:'高三',icon:'📙',sub:'高考冲刺 · 海量真题'}];
    c.innerHTML='<h3 style="margin-bottom:12px;">📚 选择你的年级</h3>'+'<div class="onboard-grade-grid">'+grades.map(function(x){var sel=onboardData.grade===x.g?' selected':'';return'<div class="onboard-grade-card'+sel+'" onclick="onboardPickGrade(\''+x.g+'\')"><span class="og-icon">'+x.icon+'</span><span class="og-label">'+x.g+'</span><span class="og-sub">'+x.sub+'</span></div>';}).join('')+'</div>';
  } else if(onboardStep===2){
    var subs=Object.keys(SUBJECT_CONFIG);
    c.innerHTML='<h3 style="margin-bottom:12px;">🎯 你想重点提升哪些科目？</h3><p style="font-size:12px;color:var(--sub);margin-bottom:12px;">可多选，不选则默认全部科目</p>'+'<div class="onboard-subj-tags">'+subs.map(function(s){var sc=SUBJECT_CONFIG[s];var sel=onboardData.weakSubjects.indexOf(s)>=0?' selected':'';return'<span class="onboard-subj-tag'+sel+'" onclick="onboardPickSubj(\''+s+'\')">'+sc.icon+' '+sc.name+'</span>';}).join('')+'</div>';
  } else if(onboardStep===3){
    var diffs=[{v:2,icon:'⭐',label:'基础巩固',desc:'适合打基础，题目简单易懂'},{v:3,icon:'⭐⭐',label:'稳步提升',desc:'中等难度，适合日常练习'},{v:4,icon:'⭐⭐⭐',label:'冲刺难题',desc:'挑战高难度，冲刺高分'},{v:0,icon:'🎯',label:'综合挑战',desc:'所有难度混合练习'}];
    c.innerHTML='<h3 style="margin-bottom:12px;">📈 选择练习难度</h3>'+'<div class="onboard-diff-options">'+diffs.map(function(d){var sel=onboardData.difficulty===d.v?' selected':'';return'<div class="onboard-diff-opt'+sel+'" onclick="onboardPickDiff('+d.v+')"><span class="od-icon">'+d.icon+'</span><div><div class="od-label">'+d.label+'</div><div class="od-desc">'+d.desc+'</div></div></div>';}).join('')+'</div>';
  }
}

function onboardPickGrade(g){onboardData.grade=g;updateOnboardUI()}
function onboardPickSubj(s){
  var i=onboardData.weakSubjects.indexOf(s);
  if(i>=0)onboardData.weakSubjects.splice(i,1);
  else onboardData.weakSubjects.push(s);
  updateOnboardUI();
}
function onboardPickDiff(v){onboardData.difficulty=v;updateOnboardUI()}

function onboardNext(){
  if(onboardStep<3){onboardStep++;updateOnboardUI();return}
  // 完成采访
  if(onboardData.weakSubjects.length===0){
    var cfg=GRADE_CONFIG[onboardData.grade];
    if(cfg)onboardData.weakSubjects=cfg.subjects.slice(0,6);
  }
  localStorage.setItem(userKey('profile'),JSON.stringify(onboardData));
  G.grade=onboardData.grade;
  G.subj=onboardData.weakSubjects[0]||'math';
  G.difficulty=onboardData.difficulty;
  localStorage.setItem(userKey('grade'),G.grade);
  localStorage.setItem(userKey('subj'),G.subj);
  localStorage.setItem(userKey('difficulty'),G.difficulty);
  enterApp();
}

function onboardPrev(){if(onboardStep>1){onboardStep--;updateOnboardUI()}}

function enterApp(){
  el('loginModal').classList.add('hidden');
  // 保存用户信息
  localStorage.setItem(userKey('last_user'),G.username);
  if(G.sessionToken)localStorage.setItem(userKey('session_token'),G.sessionToken);
  if(G.sessionExpires)localStorage.setItem(userKey('session_expires'),G.sessionExpires);
  // 数据迁移
  if(!localStorage.getItem(userKey('migrated'))){
    ['learn_xp','learn_streak','learn_grade','learn_subj','learn_wrongbook','learn_daily'].forEach(function(k){
      var old=localStorage.getItem(k);
      if(old!==null){localStorage.setItem(userKey(k),old);localStorage.removeItem(k)}
    });
    localStorage.setItem(userKey('migrated'),'1');
  }
  updateUserUI();
  doInitSteps();
}

function updateUserUI(){
  var n=el('userName');if(n)n.textContent=G.username||'点击登录';
  var u=el('userBtn');if(u)u.title='当前用户: '+(G.username||'未登录')+' (点击切换)';
}

function doInitSteps(){
  // 执行原来的 init 步骤（数据加载和渲染）
  var dbg = el('qzBody'); if(dbg) dbg.innerHTML = '⏳ 正在初始化题库...';
  loadWrongBook();

  // Gaokao 数据合并
  if(typeof gaokaoQuestions!=='undefined' && gaokaoQuestions.length>0){
    gaokaoQuestions.forEach(function(q){
      if(!q.grade) q.grade = '高三';
      if(!q.difficulty) q.difficulty = 3;
      if(!q.steps) q.steps = [];
      if(!q.source) q.source = '安徽高考真题';
    });
  }
  try{
    if(typeof gaokaoQuestions!=='undefined' && gaokaoQuestions.length>0){
      var gkMap = {};
      gaokaoQuestions.forEach(function(q){
        var s = q.subject;
        if(!gkMap[s]) gkMap[s] = [];
        gkMap[s].push(q);
      });
      var gaoSan = allQuestionsByGrade['高三'] || {};
      for(var s in gkMap){
        if(!gaoSan[s]) gaoSan[s] = [];
        var existIds = {};
        gaoSan[s].forEach(function(q){existIds[q.id] = true;});
        gkMap[s].forEach(function(q){if(!existIds[q.id]) gaoSan[s].push(q);});
      }
      allQuestionsByGrade['高三'] = gaoSan;
    }
    if(!allQuestionsByGrade['高三'] || Object.keys(allQuestionsByGrade['高三']).length===0){
      if(typeof DEMO_2025!=='undefined') allQuestionsByGrade['高三'] = DEMO_2025;
    }
  }catch(e){console.warn('gaokao merge error:',e);}

  // 中考数据合并
  try{
    if(typeof anhuiZhongkaoQuestions!=='undefined' && anhuiZhongkaoQuestions.length>0){
      var zkMap = {};
      anhuiZhongkaoQuestions.forEach(function(q){
        var s = q.subject;
        if(!zkMap[s]) zkMap[s] = [];
        zkMap[s].push(q);
      });
      var chuZhong = allQuestionsByGrade['初中'] || {};
      for(var s in zkMap){
        if(!chuZhong[s]) chuZhong[s] = [];
        var existIds2 = {};
        chuZhong[s].forEach(function(q){existIds2[q.id] = true;});
        zkMap[s].forEach(function(q){if(!existIds2[q.id]) chuZhong[s].push(q);});
      }
      allQuestionsByGrade['初中'] = chuZhong;
    }
  }catch(e){console.warn('zhongkao merge error:',e);}

  // 恢复用户数据
  G.xp = parseInt(localStorage.getItem(userKey('xp'))||'0');
  G.streak = parseInt(localStorage.getItem(userKey('streak'))||'0');
  G.grade = localStorage.getItem(userKey('grade')) || '初中';
  G.subj = localStorage.getItem(userKey('subj')) || 'math';
  G.difficulty = parseInt(localStorage.getItem(userKey('difficulty'))||'0');
  try{
    var prof=JSON.parse(localStorage.getItem(userKey('profile'))||'{}');
    if(prof.weakSubjects&&prof.weakSubjects.length>0&&prof.weakSubjects.indexOf(G.subj)===-1){
      G.subj=prof.weakSubjects[0];
    }
    if(prof.difficulty)G.difficulty=prof.difficulty;
  }catch(e){}

  // 合并高一提库
  if(typeof gaoyiQuestions!=='undefined' && gaoyiQuestions.length>0){
    gaoyiQuestions.forEach(function(q){
      var gd = allQuestionsByGrade['高一']; if(!gd) gd = allQuestionsByGrade['高一'] = {};
      if(!gd[q.subject]) gd[q.subject] = [];
      var dup = false;
      for(var i=0;i<gd[q.subject].length;i++){if(gd[q.subject][i].id===q.id){dup=true;break;}}
      if(!dup) gd[q.subject].push(q);
    });
  }
  // 合并高二提库
  if(typeof gaoerQuestions!=='undefined' && gaoerQuestions.length>0){
    gaoerQuestions.forEach(function(q){
      var gd = allQuestionsByGrade['高二']; if(!gd) gd = allQuestionsByGrade['高二'] = {};
      if(!gd[q.subject]) gd[q.subject] = [];
      var dup = false;
      for(var i=0;i<gd[q.subject].length;i++){if(gd[q.subject][i].id===q.id){dup=true;break;}}
      if(!dup) gd[q.subject].push(q);
    });
  }
  // 合并生成题目（高考/中考/专家题）
  if(typeof generatedQuestions!=='undefined' && generatedQuestions.length>0){
    generatedQuestions.forEach(function(q){
      var gd = allQuestionsByGrade[q.grade]; if(!gd) gd = allQuestionsByGrade[q.grade] = {};
      if(!gd[q.subject]) gd[q.subject] = [];
      var dup = false;
      for(var i=0;i<gd[q.subject].length;i++){if(gd[q.subject][i].id===q.id){dup=true;break;}}
      if(!dup) gd[q.subject].push(q);
    });
  }
  // 合并难题
  if(typeof hardQuestions!=='undefined' && hardQuestions.length>0){
    hardQuestions.forEach(function(q){
      var gd = allQuestionsByGrade[q.grade];
      if(!gd) gd = allQuestionsByGrade[q.grade] = {};
      if(!gd[q.subject]) gd[q.subject] = [];
      var dup = false;
      for(var i=0;i<gd[q.subject].length;i++){if(gd[q.subject][i].id===q.id){dup=true;break;}}
      if(!dup) gd[q.subject].push(q);
    });
  }

  renderGradeNav();renderSj();loadQ();renderHeroBanner();
  updateBadge();bindEv();updateXp();updateStreak();updateDailyStats();
}

// ═══════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════
function init(){
  // 检查是否有有效会话
  var savedToken=localStorage.getItem(userKey('session_token'));
  var savedUser=localStorage.getItem(userKey('last_user'));
  if(savedToken&&savedUser){
    G.username=savedUser;
    G.sessionToken=savedToken;
    fetch('/api/check_session',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({session_token:savedToken})
    })
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.success){
        G.totalSeconds=data.remaining_seconds;
        G.sessionExpires=data.expires_at;
        startTimer(data.remaining_seconds);
        updateUserUI();
        doInitSteps();
      } else {
        localStorage.removeItem(userKey('session_token'));
        showLoginModal();
      }
    })
    .catch(function(){showLoginModal();});
    return;
  }
  // 无会话 → 显示登录
  showLoginModal();

  // 1. 从 localStorage 加载错题本
  loadWrongBook();

  // 2. 为 gaokao_questions 批量添加 grade 字段（高三）
  if(typeof gaokaoQuestions!=='undefined' && gaokaoQuestions.length>0){
    gaokaoQuestions.forEach(function(q){
      if(!q.grade) q.grade = '高三';
      if(!q.difficulty) q.difficulty = 3;
      if(!q.steps) q.steps = [];
      if(!q.source) q.source = '安徽高考真题';
    });
  }

  // 3. 将 gaokao 数据按科目注入 allQuestionsByGrade['高三']
  try{
    if(typeof gaokaoQuestions!=='undefined' && gaokaoQuestions.length>0){
      var gkMap = {};
      gaokaoQuestions.forEach(function(q){
        var s = q.subject;
        if(!gkMap[s]) gkMap[s] = [];
        gkMap[s].push(q);
      });
      // 合并：gaokao 数据追加到高三已有数据后面
      var gaoSan = allQuestionsByGrade['高三'] || {};
      for(var s in gkMap){
        if(!gaoSan[s]) gaoSan[s] = [];
        // 去重：按 id 去重后合并
        var existIds = {};
        gaoSan[s].forEach(function(q){existIds[q.id] = true;});
        gkMap[s].forEach(function(q){
          if(!existIds[q.id]) gaoSan[s].push(q);
        });
      }
      allQuestionsByGrade['高三'] = gaoSan;
    }
    // 如果高三仍然为空，使用 DEMO 数据兜底
    if(!allQuestionsByGrade['高三'] || Object.keys(allQuestionsByGrade['高三']).length===0){
      if(typeof DEMO_2025!=='undefined') allQuestionsByGrade['高三'] = DEMO_2025;
    }
  }catch(e){console.warn('gaokao merge error:',e);toast('⚠️ 高考题库加载失败，使用备用数据');}

  // 4. 预科数据注入（暂不可用 — anhuiYukeQuestions 数据文件尚未创建）
  // 待数据就绪后取消注释:
  // try{
  //   if(typeof anhuiYukeQuestions!=='undefined' && anhuiYukeQuestions.length>0){
  //     var ykMap = {};
  //     anhuiYukeQuestions.forEach(function(q){
  //       var s = q.subject;
  //       if(!ykMap[s]) ykMap[s] = [];
  //       ykMap[s].push(q);
  //     });
  //     allQuestionsByGrade['预科'] = ykMap;
  //     if(!GRADE_CONFIG['预科']){
  //       GRADE_CONFIG['预科'] = {icon:'🚀', subjects:['math','phys','chem','engl'], label:'预科'};
  //     }
  //   }
  // }catch(e){console.warn('yuke merge error:',e);}

  // 5. 将安徽中考数据注入初中
  try{
    if(typeof anhuiZhongkaoQuestions!=='undefined' && anhuiZhongkaoQuestions.length>0){
      var zkMap = {};
      anhuiZhongkaoQuestions.forEach(function(q){
        var s = q.subject;
        if(!zkMap[s]) zkMap[s] = [];
        zkMap[s].push(q);
      });
      var chuZhong = allQuestionsByGrade['初中'] || {};
      for(var s in zkMap){
        if(!chuZhong[s]) chuZhong[s] = [];
        var existIds2 = {};
        chuZhong[s].forEach(function(q){existIds2[q.id] = true;});
        zkMap[s].forEach(function(q){
          if(!existIds2[q.id]) chuZhong[s].push(q);
        });
      }
      allQuestionsByGrade['初中'] = chuZhong;
    }
  }catch(e){console.warn('zhongkao merge error:',e);toast('⚠️ 中考题库加载失败');}

  // 6. 恢复用户数据
  G.xp = parseInt(localStorage.getItem(userKey('xp'))||'0');
  G.streak = parseInt(localStorage.getItem(userKey('streak'))||'0');
  G.grade = localStorage.getItem(userKey('grade')) || '初中';
  G.subj = localStorage.getItem(userKey('subj')) || 'math';
  G.difficulty = parseInt(localStorage.getItem(userKey('difficulty'))||'0');

  // 7. 渲染界面
  renderGradeNav();
  renderSj();
  loadQ();
  renderHeroBanner();
  updateBadge();
  bindEv();
  updateXp();
  updateStreak();
  updateDailyStats();
}

function bindEv(){
  var gd=el('gdNav');if(gd)gd.addEventListener('click',function(e){var b=e.target.closest('.gd-btn');if(b)navGd(b.dataset.grade);});
  document.querySelectorAll('.ic-btn').forEach(function(b){b.addEventListener('click',function(){var p=b.dataset.panel;if(G.panel===p){closePn();return;}openPn(p);});});
}

// ═══════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════
function navGd(g){
  G.grade=g; G.subj=(GRADE_CONFIG[g]||{}).subjects[0]||'math';
  localStorage.setItem(userKey('grade'),g); localStorage.setItem(userKey('subj'),G.subj);
  document.querySelectorAll('.gd-btn').forEach(function(b){b.classList.remove('active');});
  var b=document.querySelector('.gd-btn[data-grade="'+g+'"]');if(b)b.classList.add('active');
  renderSj();loadQ();closePn();renderHeroBanner();
  // 滚动到顶部
  window.scrollTo({top:0,behavior:'smooth'});
}

function navSj(s){G.subj=s;localStorage.setItem(userKey('subj'),s);renderSj();loadQ();closePn();window.scrollTo({top:0,behavior:'smooth'});}

function renderGradeNav(){
  var n=el('gdNav');if(!n)return;
  var grades = ['初中','高一','高二','高三'];
  var h='';
  for(var i=0;i<grades.length;i++){
    var g=grades[i];
    var cfg=GRADE_CONFIG[g]||{icon:'📚',label:g};
    var active = (g===G.grade)?' active':'';
    h+='<button class="gd-btn'+active+'" data-grade="'+g+'">'+cfg.icon+' '+cfg.label+'</button>';
  }
  n.innerHTML=h;
}

function renderSj(){
  var n=el('sjNav');if(!n)return;
  var cfg=GRADE_CONFIG[G.grade];
  if(!cfg){n.innerHTML='<div style="text-align:center;padding:10px;color:var(--muted);">暂无数据</div>';return;}
  var subs=cfg.subjects;var h='';
  for(var i=0;i<subs.length;i++){
    var s=subs[i];var c=SUBJECT_CONFIG[s];if(!c)continue;
    var cnt=0;var gd=allQuestionsByGrade[G.grade];
    if(gd&&gd[s]&&Array.isArray(gd[s]))cnt=gd[s].length;
    h+='<button class="sj-tag'+(s===G.subj?' active':'')+'" onclick="navSj(\''+s+'\')">'+c.icon+' '+c.name+'<span class="ct">'+cnt+'题</span></button>';
  }
  n.innerHTML=h||'<div style="text-align:center;padding:10px;color:var(--muted);">暂无科目</div>';
}

function renderHeroBanner(){
  var main = el('main'); if(!main) return;
  // 移除旧横幅
  var old = main.querySelector('.hero-banner');
  if(old) old.remove();
  var cfg = GRADE_CONFIG[G.grade];
  if(!cfg) return;
  var gradeClass = {'初中':'junior','高一':'senior1','高二':'senior2','高三':'senior3'}[G.grade]||'junior';
  // 统计题目总数
  var totalQ = 0;
  var gd = allQuestionsByGrade[G.grade];
  if(gd) for(var s in gd){if(Array.isArray(gd[s])) totalQ += gd[s].length;}
  var banner = document.createElement('div');
  banner.className = 'hero-banner '+gradeClass;
  banner.innerHTML = '<div class="hero-icon">'+cfg.icon+'</div><div class="hero-title">'+cfg.label+' · 学习之旅</div><div class="hero-sub">共 '+totalQ+' 道题目 · '+(SUBJECT_CONFIG[G.subj]||{}).name+' 专项训练</div><div class="hero-progress">🎯 每天进步一点点，坚持就是胜利！</div>';
  main.insertBefore(banner, main.firstChild);
}

// ═══════════════════════════════════════════
// TYPE FILTER
// ═══════════════════════════════════════════
function renderTp(){
  var bar=el('tpTags');if(!bar)return;var gd=allQuestionsByGrade[G.grade];
  var raw=(gd&&gd[G.subj]&&Array.isArray(gd[G.subj]))?gd[G.subj]:[];
  if(!raw.length){bar.innerHTML='';return;}
  var set={};for(var i=0;i<raw.length;i++){set[raw[i].type||'选择题']=true;}var types=['all'];for(var t in set)types.push(t);
  var lb={all:'全部',选择题:'选择题',填空题:'填空题',解答题:'解答题',完形填空:'完形填空',七选五阅读:'七选五',阅读理解:'阅读理解',短文改错:'短文改错',语法填空:'语法填空'};
  var h='';for(var i=0;i<types.length;i++){var t=types[i];var cnt=t==='all'?raw.length:raw.filter(function(q){return(q.type||'选择题')===t;}).length;h+='<button class="tp-tag'+(G.type===t?' active':'')+'" onclick="filterTp(\''+t+'\')">'+(lb[t]||t)+' ('+cnt+')</button>';}
  bar.innerHTML=h;
}
function filterTp(t){G.type=t;loadQ();}

// ═══════════════════════════════════════════
// QUIZ ENGINE
// ═══════════════════════════════════════════
function loadQ(){
  try{
    var gd=allQuestionsByGrade[G.grade];
    var raw=(gd&&gd[G.subj]&&Array.isArray(gd[G.subj]))?gd[G.subj].slice():[];
    if(G.type!=='all')raw=raw.filter(function(q){return(q.type||'选择题')===G.type;});
    // 难度筛选（基于用户偏好）
    if(G.difficulty>0)raw=raw.filter(function(q){return(q.difficulty||2)>=G.difficulty;});
    // 如果没有匹配难度的题目，回退到全部
    if(raw.length===0&&G.difficulty>0){
      raw=(gd&&gd[G.subj]&&Array.isArray(gd[G.subj]))?gd[G.subj].slice():[];
      if(G.type!=='all')raw=raw.filter(function(q){return(q.type||'选择题')===G.type;});
    }
    if(!raw.length){showDone();return;}
    // 个性化排序：薄弱科目优先
    try{
      var prof=JSON.parse(localStorage.getItem(userKey('profile'))||'{}');
      if(prof.weakSubjects&&prof.weakSubjects.indexOf(G.subj)>=0){
        // 当前科目是薄弱科目，优先展示
        raw.sort(function(a,b){return(b.difficulty||2)-(a.difficulty||2);});
      }
    }catch(e){}
    shuffle(raw);G.qs=raw;G.idx=0;G.done=false;G.streakHit=0;
    renderTp();
    var qa=el('qzArea');if(qa)qa.classList.remove('hidden');
    var qd=el('qzDone');if(qd)qd.classList.add('hidden');
    renderQ();
  }catch(e){console.warn('loadQ error:',e);toast('⚠️ 题目加载异常，请刷新重试');}
}

function renderQ(){
  try{
    if(G.idx>=G.qs.length){showDone();return;}
    var q=G.qs[G.idx];G.done=false;if(!q){nextQ();return;}
    var total=G.qs.length;
    var pb=el('pgBar');if(pb)pb.style.width=(G.idx/total*100)+'%';
    var pn=el('pgNum');if(pn)pn.textContent=(G.idx+1)+'/'+total;
    var sh=el('streakHit');if(sh)sh.textContent=G.streakHit||0;

    var ge=el('qzGrade');if(ge)ge.textContent=G.grade;
    var su=el('qzSubj');if(su)su.textContent=(SUBJECT_CONFIG[G.subj]||{}).name||G.subj;
    var ty=el('qzType');if(ty)ty.textContent=q.type||'选择题';
    var di=el('qzDiff');if(di)di.textContent='⭐'.repeat(q.difficulty||1);
    var to=el('qzTopic');if(to)to.textContent=(q.topic||'')+(q.year?' · '+q.year+'年':'')+(q.source?' · '+q.source:'');

    var bd=el('qzBody');if(bd)bd.innerHTML=q.question||'';
    var oc=el('qzOpts');if(!oc)return;
    var opts=q.options;
    if(opts&&Array.isArray(opts)&&opts.length>0){
      var labels=['A','B','C','D','E','F'];var h='';
      for(var i=0;i<opts.length;i++){h+='<div class="opt" onclick="pick('+i+')"><span class="lbl">'+(labels[i]||(i+1))+'</span><span>'+opts[i]+'</span></div>';}
      oc.innerHTML=h;oc.classList.remove('hidden');
    }else{
      oc.innerHTML='<input class="chat-in" id="fillIn" placeholder="请输入你的答案..." style="width:100%;padding:14px;border-radius:16px;border:2px solid var(--brd);font-size:15px;">'+'<button class="btn pri" onclick="checkFill()" style="width:100%;margin-top:10px;">✅ 提交答案</button>';
    }
    var fb=el('qzFb');if(fb)fb.classList.add('hidden');
    renderMath(el('qzCard'));
    var card=el('qzCard');if(card)card.scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){console.warn('renderQ error:',e);}
}

function pick(idx){
  if(G.done||!G.qs[G.idx])return;G.done=true;
  var q=G.qs[G.idx];
  var corr=String(q.answer||'').trim().charAt(0).toUpperCase();
  var sel=String.fromCharCode(65+idx);
  var ok=(sel===corr);
  G.lastAnswer=sel;

  var all=document.querySelectorAll('#qzOpts .opt');
  all.forEach(function(o,i){o.classList.add('done');var l=String.fromCharCode(65+i);if(l===corr)o.classList.add('ok');if(i===idx&&!ok)o.classList.add('err');});

  if(ok){G.streakHit=(G.streakHit||0)+1;addXp(10);spawnConfetti();recordAnswer(true);}
  else{G.streakHit=0;addWrong(q,sel);recordAnswer(false);}
  showFb(ok);
  var sh=el('streakHit');if(sh)sh.textContent=G.streakHit||0;
}

function checkFill(){
  if(G.done)return;G.done=true;var inp=el('fillIn');if(!inp)return;var q=G.qs[G.idx];if(!q)return;
  var userAns = inp.value.trim();
  var correctAns = String(q.answer||'').trim();
  // 尝试多种匹配方式
  var ok = (userAns.toLowerCase() === correctAns.toLowerCase());
  if(!ok){
    // 数值比较
    var un = parseFloat(userAns), cn = parseFloat(correctAns);
    if(!isNaN(un) && !isNaN(cn) && Math.abs(un-cn)<0.001) ok = true;
  }
  if(ok){G.streakHit=(G.streakHit||0)+1;addXp(10);spawnConfetti();recordAnswer(true);}
  else{G.streakHit=0;addWrong(q,userAns);recordAnswer(false);}
  showFb(ok);
}

function showFb(ok){
  var q=G.qs[G.idx];if(!q)return;
  var fb=el('qzFb'),head=el('fbHead'),body=el('fbBody');
  if(!fb||!head||!body)return;
  fb.classList.remove('hidden','ok','err');fb.classList.add(ok?'ok':'err');

  if(ok){
    head.innerHTML='🎉 回答正确！太棒了！';
    var h='<div style="font-size:15px;font-weight:700;margin-bottom:10px;color:#3CB882;">✅ 正确答案：'+String(q.answer||'')+'</div>';
    h+='<div style="background:#fff;padding:14px;border-radius:12px;line-height:1.9;font-size:14px;">';
    h+='<div style="font-weight:700;margin-bottom:6px;">📝 解析</div>';
    h+='<div>'+String(q.explanation||'暂无解析')+'</div></div>';
    body.innerHTML=h;
  }else{
    head.innerHTML='😅 回答错误，别灰心！看看解析吧～';
    var h='<div style="font-size:15px;font-weight:700;margin-bottom:12px;padding:12px 16px;background:rgba(255,255,255,.7);border-radius:12px;">';
    h+='❌ 你的答案：<span style="color:var(--red);">'+(G.lastAnswer||'?')+'</span> &nbsp;|&nbsp; ';
    h+='✅ 正确答案：<span style="color:#3CB882;">'+String(q.answer||'')+'</span></div>';
    var steps=q.steps;
    if(steps&&Array.isArray(steps)&&steps.length>0){
      h+='<div style="background:#fff;padding:14px;border-radius:12px;margin-bottom:10px;">';
      h+='<div style="font-weight:700;margin-bottom:8px;font-size:14px;">🔍 解题步骤</div>';
      for(var i=0;i<steps.length;i++){h+='<div class="stp"><span class="stp-n">'+(i+1)+'.</span> '+steps[i]+'</div>';}
      h+='</div>';
    }
    h+='<div style="background:#fff;padding:14px;border-radius:12px;line-height:1.9;font-size:14px;">';
    h+='<div style="font-weight:700;margin-bottom:6px;">📝 详细解析</div>';
    h+='<div>'+String(q.explanation||'暂无解析')+'</div></div>';
    body.innerHTML=h;
  }
  renderMath(fb);fb.scrollIntoView({behavior:'smooth',block:'nearest'});
}

function nextQ(){G.idx++;renderQ();}
function retryQ(){G.done=false;renderQ();}
function resetQ(){G.idx=0;G.done=false;var qd=el('qzDone');if(qd)qd.classList.add('hidden');var qa=el('qzArea');if(qa)qa.classList.remove('hidden');loadQ();}
function showDone(){
  var qa=el('qzArea');if(qa)qa.classList.add('hidden');
  var qd=el('qzDone');if(qd)qd.classList.remove('hidden');
  // 更新完成文案
  var h2=qd.querySelector('h2');if(h2)h2.textContent='🎉 太厉害了！全部完成！';
  var p=qd.querySelector('p');if(p)p.textContent='你已经掌握了'+(SUBJECT_CONFIG[G.subj]||{}).name+'的所有题目';
}

// ═══════════════════════════════════════════
// XP & GAMIFICATION
// ═══════════════════════════════════════════
function addXp(pts){G.xp+=pts;G.streak=(G.streak||0)+1;try{localStorage.setItem(userKey('xp'),G.xp);localStorage.setItem(userKey('streak'),G.streak);}catch(e){}updateXp();updateStreak();}
function updateXp(){var x=el('xpCount');if(x){x.textContent=G.xp;x.style.animation='none';setTimeout(function(){x.style.animation='bounceIn .5s cubic-bezier(.34,1.56,.64,1)';},10);}}
function updateStreak(){var s=el('streakCount');if(s)s.textContent=G.streak;}

var _confettiThrottle = 0;
function spawnConfetti(){
  var now = Date.now();
  if(now - _confettiThrottle < 600) return;
  _confettiThrottle = now;
  var container=el('confettiContainer');if(!container)return;
  // 限制同时最多100个confetti
  if(container.children.length > 80) return;
  var colors=['#FF6B9D','#FFB74D','#4DD9A0','#64B5F6','#B39DDB','#FF8A65','#EF5350','#FFD700','#00CED1','#FF69B4'];
  var count = Math.min(50, 100 - container.children.length);
  for(var i=0;i<count;i++){
    var piece=document.createElement('div');piece.className='confetti-piece';
    piece.style.left=Math.random()*100+'%';piece.style.top=-(Math.random()*100)+'px';
    piece.style.background=colors[Math.floor(Math.random()*colors.length)];
    piece.style.animationDelay=Math.random()*.5+'s';
    piece.style.animationDuration=(1.2+Math.random()*2)+'s';
    piece.style.width=(6+Math.random()*12)+'px';piece.style.height=(6+Math.random()*12)+'px';
    piece.style.borderRadius=Math.random()>0.5?'50%':'3px';
    container.appendChild(piece);
    setTimeout(function(){piece.remove();},2500);
  }
}

// ═══════════════════════════════════════════
// WRONG BOOK (localStorage 持久化)
// ═══════════════════════════════════════════
var wrongBook = [];

function loadWrongBook(){
  try{
    var saved = localStorage.getItem(userKey('wrongbook'));
    if(saved){wrongBook = JSON.parse(saved);}
    else{wrongBook = [];} // 不再使用硬编码示例数据
  }catch(e){wrongBook=[];}
}

function saveWrongBook(){
  try{localStorage.setItem(userKey('wrongbook'),JSON.stringify(wrongBook));}catch(e){}
}

function addWrong(q,ua){
  try{
    var exist=wrongBook.find(function(w){return w.question===q.question&&w.subject===q.subject;});
    if(exist){exist.attemptCount=(exist.attemptCount||1)+1;exist.date=dt();exist.userAnswer=ua;exist.mastered=false;}
    else{wrongBook.unshift({id:'w'+Date.now(),grade:q.grade||G.grade,subject:q.subject,topic:q.topic||'',question:q.question,options:q.options||[],userAnswer:ua,correctAnswer:q.answer,explanation:q.explanation||'',date:dt(),mastered:false,attemptCount:1});}
    saveWrongBook();
    updateBadge();
    toast('📕 已加入错题本，加油攻克它！');
  }catch(e){console.warn('addWrong error:',e);}
}

function updateBadge(){var b=el('wrongBadge');if(!b)return;var c=wrongBook.filter(function(w){return!w.mastered;}).length;b.textContent=c;b.style.display=c>0?'flex':'none';}

// ═══════════════════════════════════════════
// DAILY STATS (localStorage)
// ═══════════════════════════════════════════
function recordAnswer(correct){
  var today = dt();
  var stats = {};
  try{stats = JSON.parse(localStorage.getItem(userKey('daily'))||'{}');}catch(e){}
  if(!stats[today]) stats[today] = {total:0,correct:0,subjects:{}};
  stats[today].total++;
  if(correct) stats[today].correct++;
  if(!stats[today].subjects[G.subj]) stats[today].subjects[G.subj] = {total:0,correct:0};
  stats[today].subjects[G.subj].total++;
  if(correct) stats[today].subjects[G.subj].correct++;
  // 只保留最近30天
  var keys = Object.keys(stats).sort();
  if(keys.length>30){delete stats[keys[0]];}
  try{localStorage.setItem(userKey('daily'),JSON.stringify(stats));}catch(e){}
}

function updateDailyStats(){
  var today = dt();
  var stats = {};
  try{stats = JSON.parse(localStorage.getItem(userKey('daily'))||'{}');}catch(e){}
  var todayStats = stats[today] || {total:0,correct:0};
  // 更新日期显示
  var dateEl = document.getElementById('funDate');
  if(dateEl) dateEl.textContent = '📅 '+today;
  // 更新目标
  var goalEl = document.getElementById('funTodayGoal');
  if(goalEl) goalEl.innerHTML = '🎯 今日已做：<b>'+todayStats.total+'</b>题';
  // 更新高考倒计时
  var cdEl = document.getElementById('funCountdown');
  if(cdEl){
    var now=new Date();var gaokao=new Date(2027,5,7);
    var diff=Math.ceil((gaokao-now)/(1000*60*60*24));
    cdEl.innerHTML = '⏳ 距2027高考<b>'+diff+'天</b>';
  }
  // 更新funStats（兼容旧代码）
  var el = document.getElementById('funStats');
  if(el){
    var rateText = todayStats.total>0 ? ' · 📈 正确率：<b>'+Math.round((todayStats.correct||0)/todayStats.total*100)+'%</b>' : '';
    el.querySelector('.fun-stat:last-child') && (function(){
      // 更新已有子元素而不是全部替换
    })();
  }
}

// ═══════════════════════════════════════════
// PANELS
// ═══════════════════════════════════════════
var pnMap={wrongbook:'pnWrong',errorrank:'pnRank',aichat:'pnAI',report:'pnRpt',hyperframes:'pnHF'};
function openPn(name){
  closePn();G.panel=name;var pn=el(pnMap[name]);if(pn)pn.classList.remove('hidden');
  document.querySelectorAll('.ic-btn').forEach(function(b){b.style.background='';});
  var btn=document.querySelector('.ic-btn[data-panel="'+name+'"]');if(btn)btn.style.background='var(--pink-lt)';
  try{switch(name){case'wrongbook':renderWB();break;case'errorrank':renderER();break;case'aichat':initChat();break;case'report':renderRpt();break;case'hyperframes':initHF();break;}}catch(e){}
}
function closePn(){if(!G.panel)return;var pn=el(pnMap[G.panel]);if(pn)pn.classList.add('hidden');document.querySelectorAll('.ic-btn').forEach(function(b){b.style.background='';});G.panel=null;}

function renderWB(){
  var ft=el('wrongFt'),ls=el('wrongLs');if(!ft||!ls)return;
// 错题本年级列表
var wbGrades = ['初中','高一','高二','高三'];
// ... rest of wrong book filter
  ft.innerHTML='<select id="wbG" onchange="applyWB()"><option value="all">全部年级</option>'+wbGrades.map(function(g){return'<option value="'+g+'">'+g+'</option>';}).join('')+'</select><select id="wbS" onchange="applyWB()"><option value="all">全部科目</option>'+Object.keys(SUBJECT_CONFIG).map(function(k){return'<option value="'+k+'">'+SUBJECT_CONFIG[k].name+'</option>';}).join('')+'</select><select id="wbM" onchange="applyWB()"><option value="all">全部</option><option value="no">❌ 未掌握</option><option value="yes">✅ 已掌握</option></select>';
  applyWB();
}
function applyWB(){
  var gf=(el('wbG')||{}).value||'all',sf=(el('wbS')||{}).value||'all',mf=(el('wbM')||{}).value||'all';
  var f=wrongBook.slice();if(gf!=='all')f=f.filter(function(w){return w.grade===gf;});if(sf!=='all')f=f.filter(function(w){return w.subject===sf;});if(mf==='no')f=f.filter(function(w){return!w.mastered;});if(mf==='yes')f=f.filter(function(w){return w.mastered;});
  var c=el('wrongLs');if(!c)return;
  if(!f.length){c.innerHTML='<div style="text-align:center;padding:50px;color:var(--muted);">🎉 暂无错题，继续保持！</div>';return;}
  c.innerHTML=f.map(function(w){var sn=(SUBJECT_CONFIG[w.subject]||{}).name||w.subject;return'<div class="wi'+(w.mastered?' ok':'')+'"><div class="wi-t"><span class="qz-badge grade">'+(w.grade||'高三')+'</span><span class="qz-badge subj">'+sn+'</span>'+(w.topic?'<span class="qz-badge topic">'+w.topic+'</span>':'')+'<span style="font-size:11px;color:var(--muted);margin-left:auto;">📅'+w.date+' · 错'+(w.attemptCount||1)+'次</span></div><div class="wi-q">'+w.question+'</div><div class="wi-a"><span class="ua">❌ '+w.userAnswer+'</span><span class="ca">✅ '+w.correctAnswer+'</span></div><div class="wi-e">💡 '+w.explanation+'</div><div class="wi-acts"><button class="btn '+(w.mastered?'gho':'pri')+' sm" onclick="togWB(\''+w.id+'\')">'+(w.mastered?'标为未掌握':'✅ 标为已掌握')+'</button><button class="btn gho sm" onclick="delWB(\''+w.id+'\')">🗑️</button></div></div>';}).join('');
}
function togWB(id){var w=wrongBook.find(function(x){return x.id===id;});if(w){w.mastered=!w.mastered;saveWrongBook();applyWB();updateBadge();}}
function delWB(id){var i=wrongBook.findIndex(function(x){return x.id===id;});if(i!==-1){wrongBook.splice(i,1);saveWrongBook();applyWB();updateBadge();}}

function renderER(){
  var c=el('rankLs');if(!c)return;
  if(!errorProneQuestions||errorProneQuestions.length===0){c.innerHTML='<div style="text-align:center;padding:50px;color:var(--muted);">📊 暂无易错题数据</div>';return;}
  c.innerHTML=errorProneQuestions.map(function(q){return'<div class="ri"><div class="wi-t"><span class="rnk">#'+q.rank+'</span><span class="qz-badge grade">'+q.grade+'</span><span class="qz-badge subj">'+(SUBJECT_CONFIG[q.subject]||{}).name+'</span><span style="color:var(--red);font-weight:700;">'+q.errorRate+'%</span></div><div class="wi-q">'+q.question+'</div><div style="font-size:13px;margin:6px 0;"><span style="color:var(--red);">❌ '+q.commonMistake+'</span> &nbsp; <span style="color:#3CB882;">✅ '+q.correctAnswer+'</span></div><div class="wi-e">💡 '+q.avoidTip+'</div></div>';}).join('');
}

// ═══════════════════════════════════════════
// AI CHAT — 真实 DeepSeek API
// ═══════════════════════════════════════════
var chatMessages = [];

function initChat(){
  var s=el('chatSend'),i=el('chatIn');
  if(s)s.onclick=sendChat;
  if(i)i.onkeydown=function(e){if(e.key==='Enter')sendChat();};
  var q=el('chatQk');if(q)q.onclick=function(e){var b=e.target.closest('.qk-btn');if(b){addMsg(b.dataset.q,'user');sendRealChat(b.dataset.q);}};
  // 显示历史消息
  renderChatMsgs();
}

function renderChatMsgs(){
  var c=el('chatMs');if(!c)return;
  if(chatMessages.length===0){
    c.innerHTML='<div class="chat-b ai">👋 嘿！我是你的AI学习伙伴～<br><br>我可以帮你：<br>📖 讲解知识点<br>🔍 分析错题原因<br>💡 推荐练习题<br>📝 解答学科疑问<br><br>选错题我会帮你分析，加油！💪</div>';
    return;
  }
  c.innerHTML=chatMessages.map(function(m){return'<div class="chat-b '+m.role+'">'+m.content.replace(/\n/g,'<br>')+'</div>';}).join('');
  c.scrollTop=c.scrollHeight;
}

function addMsg(t,type){
  chatMessages.push({role:type,content:t});
  if(chatMessages.length>30)chatMessages.splice(0,chatMessages.length-30);
  renderChatMsgs();
}

async function sendChat(){
  var i=el('chatIn');if(!i||!i.value.trim())return;
  var text=i.value.trim();i.value='';
  addMsg(text,'user');
  await sendRealChat(text);
}

async function sendRealChat(userMsg){
  var typing=el('chatTyping');if(typing)typing.style.display='block';
  try{
    var res=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        messages:[
          {role:'system',content:'你是"AI智慧学伴"的学习助手。你帮助中学生（初中到高三）解答学科问题。请用中文回答，语气亲切、耐心，像一位学长/学姐。回答控制在200-400字，多用具体例子。学科包括：数学、物理、化学、生物、英语、语文、历史、地理、政治。如果学生问的是具体题目，先引导思考不要直接给答案。结尾可以给一个学习建议或小技巧。'},
          {role:'user',content:userMsg}
        ]
      }),
    });
    var data=await res.json();
    if(typing)typing.style.display='none';
    if(data.success){
      addMsg(data.content,'ai');
    }else{
      // 降级到本地回复
      addMsg(getLocalReply(userMsg),'ai');
    }
  }catch(e){
    if(typing)typing.style.display='none';
    addMsg(getLocalReply(userMsg),'ai');
  }
}

function getLocalReply(tx){
  var r='收到！我可以帮你：\n📚 讲解知识点\n🔍 分析错题原因\n💡 推荐练习题\n\n请告诉我具体需要什么帮助！';
  if(tx.indexOf('不懂')>=0||tx.indexOf('不会')>=0)r='好的！请把题目发给我，我会帮你一步步分析～\n\n记住：\n1. 先看题目问什么\n2. 列出已知条件\n3. 想想考的是哪个知识点\n4. 套用公式/方法\n\n把题目发过来吧！😊';
  else if(tx.indexOf('错因')>=0||tx.indexOf('错题')>=0)r='分析错因很重要！常见错误类型：\n\n📊 概念混淆（35%）— 没理解清概念就做题\n📊 计算失误（25%）— 会做但算错了\n📊 审题不清（20%）— 没看清条件\n📊 方法不当（20%）— 选了复杂的方法\n\n你的错题本里共'+wrongBook.length+'道错题，建议每天复习3-5道，重复练习直到掌握！';
  else if(tx.indexOf('推荐')>=0||tx.indexOf('练习')>=0)r='基于你的学习情况，建议：\n\n🎯 先复习错题本中的题目\n🎯 从基础题开始，逐步提升难度\n🎯 每天坚持做10-15题\n\n需要我出具体题目的话，告诉我你想练哪个科目、哪个知识点！';
  return r;
}

// ═══════════════════════════════════════════
// REPORT — 增强版
// ═══════════════════════════════════════════
function renderRpt(){
  var c=el('rptCt');if(!c)return;
  var total=0,subjTotal={};
  for(var g in allQuestionsByGrade){var gd=allQuestionsByGrade[g];for(var s in gd){if(Array.isArray(gd[s])){total+=gd[s].length;subjTotal[s]=(subjTotal[s]||0)+gd[s].length;}}}
  var mastered=wrongBook.filter(function(w){return w.mastered;}).length;
  var unm=wrongBook.length-mastered;

  // 今日统计
  var today=dt();
  var daily={};
  try{daily=JSON.parse(localStorage.getItem(userKey('daily'))||'{}');}catch(e){}
  var todayStats=daily[today]||{total:0,correct:0};
  var todayRate=todayStats.total>0?Math.round(todayStats.correct/todayStats.total*100):0;

  // 最近7天趋势
  var days=[];
  for(var i=6;i>=0;i--){var d=new Date();d.setDate(d.getDate()-i);var ds=d.toISOString().split('T')[0];var dd=daily[ds]||{total:0,correct:0};days.push({date:ds.slice(5),total:dd.total,correct:dd.correct});}
  var maxTotal=Math.max.apply(null,days.map(function(d){return d.total;}).concat([1]));

  // 各科正确率（从daily stats聚合）
  var subjRates={};
  for(var dk in daily){
    var dd2=daily[dk];
    for(var sk in dd2.subjects){
      if(!subjRates[sk])subjRates[sk]={total:0,correct:0};
      subjRates[sk].total+=dd2.subjects[sk].total;
      subjRates[sk].correct+=dd2.subjects[sk].correct;
    }
  }

  var h='<div class="rpt-g">';
  h+='<div class="rpt-c" style="border-left:3px solid var(--pink)"><div class="vl">'+total+'</div><div class="lb">📚 题库总数</div></div>';
  h+='<div class="rpt-c" style="border-left:3px solid var(--red)"><div class="vl">'+wrongBook.length+'</div><div class="lb">📕 错题总数</div></div>';
  h+='<div class="rpt-c" style="border-left:3px solid var(--mint)"><div class="vl" style="-webkit-text-fill-color:#3CB882;">'+mastered+'</div><div class="lb">✅ 已掌握</div></div>';
  h+='<div class="rpt-c" style="border-left:3px solid var(--coral)"><div class="vl" style="-webkit-text-fill-color:var(--red);">'+unm+'</div><div class="lb">🎯 待攻克</div></div>';
  h+='</div>';

  // 今日概览
  h+='<div style="margin-top:20px;background:linear-gradient(135deg,var(--pink-lt),var(--coral-lt));padding:16px 20px;border-radius:16px;">';
  h+='<strong>📊 今日学习概览</strong><br>';
  h+='<span style="font-size:14px;">今日答题：<b>'+todayStats.total+'</b> 题 · 正确：<b>'+(todayStats.correct||0)+'</b> 题 · 正确率：<b style="color:'+(todayRate>=70?'var(--mint)':'var(--red)')+'">'+todayRate+'%</b></span>';
  h+='</div>';

  // 7天趋势
  h+='<div style="margin-top:16px;"><strong>📈 近7天学习趋势</strong></div>';
  h+='<div style="display:flex;align-items:flex-end;gap:6px;height:80px;margin-top:8px;padding:0 4px;">';
  days.forEach(function(d){
    var h2=d.total>0?Math.max(8,Math.round(d.total/maxTotal*70)):4;
    var color2=d.total>0?(d.correct/d.total>=0.7?'var(--mint)':d.correct/d.total>=0.4?'var(--yellow)':'var(--red)'):'var(--brd)';
    h+='<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;">';
    h+='<span style="font-size:10px;color:var(--sub);">'+d.total+'</span>';
    h+='<div style="width:100%;max-width:40px;height:'+h2+'px;background:'+color2+';border-radius:6px 6px 0 0;transition:.3s;" title="'+d.date+'  '+d.correct+'/'+d.total+'"></div>';
    h+='<span style="font-size:9px;color:var(--muted);">'+d.date+'</span>';
    h+='</div>';
  });
  h+='</div>';

  // 各科正确率
  var subjKeys=Object.keys(subjRates).filter(function(k){return subjRates[k].total>=3;});
  if(subjKeys.length>0){
    h+='<div style="margin-top:16px;"><strong>🎯 各科目正确率</strong></div>';
    subjKeys.forEach(function(k){
      var sr=subjRates[k];var rate=Math.round(sr.correct/sr.total*100);
      var barColor=rate>=80?'var(--mint)':rate>=60?'var(--yellow)':'var(--red)';
      var sn=(SUBJECT_CONFIG[k]||{}).name||k;
      h+='<div style="display:flex;align-items:center;gap:8px;margin:6px 0;">';
      h+='<span style="width:50px;font-size:13px;">'+sn+'</span>';
      h+='<div style="flex:1;height:8px;background:var(--brd);border-radius:4px;overflow:hidden;">';
      h+='<div style="height:100%;width:'+rate+'%;background:'+barColor+';border-radius:4px;transition:width .5s;"></div></div>';
      h+='<span style="font-size:12px;font-weight:700;min-width:40px;text-align:right;">'+rate+'%</span></div>';
    });
  }

  // 错题年级分布
  h+='<div style="margin-top:16px;"><strong>📊 各年级错题分布</strong></div>';
  ['初中','高一','高二','高三'].forEach(function(g){
    var cnt=wrongBook.filter(function(w){return w.grade===g;}).length;
    var barW=Math.min(cnt*8,100);
    h+='<div style="display:flex;align-items:center;gap:8px;margin:6px 0;"><span style="width:50px;font-size:13px;">'+g+'</span><div style="flex:1;height:6px;background:var(--brd);border-radius:3px;"><div style="height:100%;width:'+barW+'%;background:'+(cnt>5?'var(--red)':cnt>2?'var(--yellow)':'var(--mint)')+';border-radius:3px;"></div></div><span style="font-size:12px;font-weight:600;">'+cnt+'题</span></div>';
  });

  // XP 等级
  var level=G.xp<100?'🌱 新手':G.xp<500?'🌿 学徒':G.xp<2000?'🌳 达人':G.xp<5000?'🏆 高手':G.xp<10000?'💎 大师':'👑 传奇';
  h+='<div style="margin-top:16px;background:linear-gradient(135deg,#FFF8EE,#FFF0E0);padding:14px 18px;border-radius:14px;">';
  h+='<strong>🏅 学习等级</strong> '+level+' · ⭐ '+G.xp+' XP · 🔥 连续 '+G.streak+' 天</div>';

  c.innerHTML=h;
}

// ═══════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════
function shuffle(a){for(var i=a.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1));var t=a[i];a[i]=a[j];a[j]=t;}}
function dt(){return new Date().toISOString().split('T')[0];}
function renderMath(el){if(!el||typeof renderMathInElement!=='function')return;try{renderMathInElement(el,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false,trust:true,strict:false});}catch(e){}}
function toast(m){
  var old=document.querySelector('.toast');if(old)old.remove();
  var t=document.createElement('div');t.className='toast success';t.textContent=m;document.body.appendChild(t);
  setTimeout(function(){t.remove();},2800);
}

// ═══════════════════════════════════════════
// HYPERFRAMES — 学习视频生成
// ═══════════════════════════════════════════
var hfEduApiBase = '/api/edu/hyperframes';

function initHF(){onHfEduTemplateChange();}
function onHfEduTemplateChange(){
  var tpl=el('hfEduTemplate').value,fields=el('hfEduFields'),custom=el('hfEduCustom'),bodyField=el('hfEduBodyField');
  if(tpl==='custom'){if(fields)fields.style.display='none';if(custom)custom.style.display='';}
  else{if(fields)fields.style.display='';if(custom)custom.style.display='none';if(bodyField)bodyField.style.display=(tpl==='eduCard')?'':'none';}
}
function showHfLoading(){var l=el('hfEduLoading'),e=el('hfEduError'),r=el('hfEduResult');if(l)l.classList.remove('hidden');if(e){e.classList.add('hidden');e.textContent='';}if(r)r.classList.add('hidden');}
function showHfError(msg){var l=el('hfEduLoading'),e=el('hfEduError'),r=el('hfEduResult');if(l)l.classList.add('hidden');if(e){e.textContent='❌ '+msg;e.classList.remove('hidden');}if(r)r.classList.add('hidden');}
function showHfResult(url){var l=el('hfEduLoading'),e=el('hfEduError'),r=el('hfEduResult'),v=el('hfEduVideo');if(l)l.classList.add('hidden');if(e)e.classList.add('hidden');if(r)r.classList.remove('hidden');if(v){v.src=url;v.load();}}

async function generateEduVideo(){
  var template=el('hfEduTemplate').value,resolution=el('hfEduResolution').value,duration=parseInt(el('hfEduDuration').value)||5,fontSize=parseInt(el('hfEduFontSize').value)||48;
  var body={template:template,resolution:resolution,duration:duration,fontSize:fontSize};
  if(template==='custom'){var html=el('hfEduHtml').value.trim();if(!html||html.length<50){toast('请粘贴完整的HTML代码');return;}body.html=html;}
  else{var title=el('hfEduTitle').value.trim();if(!title){toast('请输入主标题');return;}body.title=title;body.subtitle=el('hfEduSubtitle').value.trim();body.badge=el('hfEduBadge').value.trim();body.emoji=el('hfEduEmoji').value.trim();body.body=el('hfEduBody').value.trim();body.watermark='AI 智慧学伴';body.hashtag='#每天进步';body.cta='开始学习';}
  showHfLoading();var loadingText=el('hfEduLoadingText');if(loadingText)loadingText.textContent='正在渲染视频...（约需30-60秒）';
  try{
    var res=await fetch(hfEduApiBase,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var data=await res.json();if(!res.ok)throw new Error(data.error||data.detail||'渲染失败');
    showHfResult(data.videoUrl);toast('🎬 视频生成成功！');
  }catch(err){showHfError(err.message);}
}

document.addEventListener('DOMContentLoaded',init);
