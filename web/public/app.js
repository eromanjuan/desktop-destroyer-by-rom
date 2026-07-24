/* Desktop Destroyer — site behaviour + the in-browser playground.
   The playground is a deliberately simplified port of the real app: same layer
   model (a pristine copy you can always restore from, plus a mutable one that
   damage is drawn into), same procedural decals, far fewer particles. */

/* ─────────────────────────── weapon data ─────────────────────────── */
const WEAPONS = [
  { key:'H', ico:'carpenter', name:'Hammer',       use:'Left-click',
    text:'Caves in the screen with a spiderweb of shattered glass, throws debris, and knocks loose any shuriken or kunai stuck nearby.' },
  { key:'K', ico:'swords', name:'Katana',       use:'Drag, then release',
    text:'Draw out a stroke and let go. Leaves a clean tapered gash that bites deepest mid-swing — and cuts any bug in its path clean in two.' },
  { key:'S', ico:'flare', name:'Shuriken',      use:'Click to throw · right-click swaps',
    text:'Hurl a spinning throwing star or a point-first kunai. Both stick in the screen — until a hammer blow or a blast shakes them loose and they tumble off.' },
  { key:'G', ico:'scatter_plot', name:'Shotgun',      use:'Hold to unload',
    text:'A cone of ragged bullet holes per blast, with muzzle flash, sparks and recoil. Holding it down keeps firing.' },
  { key:'B', ico:'target', name:'Bow',          use:'Hold to draw, release',
    text:'Arrows stay stuck in your screen — a full-power shot shatters the surface. Set one alight and it chars and topples out of the display.' },
  { key:'T', ico:'terrain', name:'Rock',         use:'Click to throw',
    text:'No fuse, no charge. It arcs in, cracks whatever it lands on and chips flakes out of the surface. Throw another.' },
  { key:'N', ico:'bomb', name:'Grenade',      use:'Click to lob',
    text:'Arcs in and sits there blinking for 1.2 seconds — then craters everything nearby in fire, soot and shrapnel.' },
  { key:'P', ico:'rocket_launch', name:'RPG',   use:'Click to fire',
    text:'A rocket-propelled grenade streaks in on a smoke trail and detonates — a bigger blast than a grenade, and it sets off gasoline and planted bombs too.' },
  { key:'M', ico:'explosion', name:'Remote Bomb',  use:'Left-click plant · right-click BOOM',
    text:'Mine the desktop with charges and detonate them all at once — or let fire reach one and it goes off on its own, chaining to the rest.' },
  { key:'L', ico:'local_gas_station', name:'Gasoline', use:'Drag to pour',
    text:'Pour a slick, then light it with the flamethrower or any blast. The fire races along the trail like a fuse, burns for 10–20s, and leaves a charred scar.' },
  { key:'F', ico:'local_fire_department', name:'Flamethrower', use:'Hold and drag',
    text:'A continuous jet of fire that burns the screen to black char — and sets light to gasoline, stuck arrows and any bugs it sweeps across.' },
  { key:'U', ico:'crisis_alert', name:'Nuke Strike', use:'Lock targets · right-click launch',
    text:'Lock up to ten targets, then launch. Each nuclear missile craters roughly a fifth of the screen and sets off any gasoline or bombs in the blast.' },
  { key:'I', ico:'pest_control', name:'Bugs',   use:'Click to place · right-click swaps',
    text:'Drop ants and flies onto the screen, then hunt them. They wander until a weapon gets them — sliced, splatted, shot or burned, each its own messy way.' },
  { key:'A', ico:'brush', name:'Paintbrush',   use:'Drag to paint',
    text:'For when you would rather deface than destroy. The colour shifts through the rainbow as you drag.' },
  { key:'W', ico:'cleaning_services', name:'Washer',       use:'Scrub, or press R',
    text:'Scrubs the original desktop back into view wherever you rub, dousing gasoline and fire. Or press R to wipe the whole screen clean.' },
];

/* ─────────────────────────── icon font gate ───────────────────────────
   Material Symbols renders via ligatures, so the markup literally contains the
   word "carpenter". Reveal icons only once the font is confirmed loaded —
   otherwise a blocked or slow CDN would print those words on the page. */
(function icons(){
  const reveal = () => {
    try {
      if (document.fonts.check('24px "Material Symbols Outlined"')) {
        document.documentElement.classList.add('icons-ready');
        return true;
      }
    } catch { /* no Font Loading API — leave icons hidden, labels still read */ }
    return false;
  };
  if (!document.fonts) return;
  document.fonts.load('24px "Material Symbols Outlined"').then(reveal).catch(() => {});
  document.fonts.ready.then(reveal).catch(() => {});
  // A few late retries: fonts.ready can settle before a swap-loaded face lands.
  [400, 1200, 3000].forEach(ms => setTimeout(reveal, ms));
})();

/* ─────────────────────────── live stats ───────────────────────────
   Downloads come from GitHub's real release download counts; visits from a
   tiny counter service (a static site can't tally its own visits). Both fail
   silently to a dash so a flaky network never leaves a broken number. */
(function stats(){
  const dEl = document.getElementById('statDownloads');
  const vEl = document.getElementById('statVisits');
  if (!dEl || !vEl) return;

  const fmt = n => n.toLocaleString();
  function countUp(el, target){
    if (typeof target !== 'number' || isNaN(target)) { el.textContent = '—'; return; }
    const dur = 900, start = performance.now();
    (function step(now){
      const k = Math.min(1, (now - start) / dur);
      el.textContent = fmt(Math.floor(target * (1 - Math.pow(1 - k, 3))));
      if (k < 1) requestAnimationFrame(step);
      else el.textContent = fmt(target);
    })(start);
  }

  // Downloads: sum every release asset's count, cached 10 min so refreshes
  // don't burn through GitHub's unauthenticated hourly rate limit.
  (async function downloads(){
    try {
      const hit = JSON.parse(localStorage.getItem('dd_downloads') || 'null');
      if (hit && Date.now() - hit.t < 600000) { countUp(dEl, hit.n); return; }
      const res = await fetch('https://api.github.com/repos/eromanjuan/desktop-destroyer-by-rom/releases');
      if (!res.ok) throw 0;
      const rels = await res.json();
      let n = 0;
      rels.forEach(r => (r.assets || []).forEach(a => { n += a.download_count || 0; }));
      localStorage.setItem('dd_downloads', JSON.stringify({ n, t: Date.now() }));
      countUp(dEl, n);
    } catch { dEl.textContent = '—'; }
  })();

  // Visits: bump the counter once per page load, show the running total.
  (async function visits(){
    try {
      const res = await fetch('https://api.counterapi.dev/v1/desktopdestroyer-web/visits/up');
      if (!res.ok) throw 0;
      const j = await res.json();
      countUp(vEl, j.count);
    } catch { vEl.textContent = '—'; }
  })();
})();

/* ─────────────────────────── nav + reveal ─────────────────────────── */
(function chrome(){
  const nav = document.getElementById('nav');
  const burger = document.getElementById('burger');
  const links = document.getElementById('links');

  addEventListener('scroll', () => nav.classList.toggle('stuck', scrollY > 8), {passive:true});

  burger.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    burger.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  links.addEventListener('click', e => {
    if (e.target.tagName === 'A') {
      links.classList.remove('open');
      burger.setAttribute('aria-expanded','false');
    }
  });

  // Highlight whichever section is on screen.
  const anchors = [...links.querySelectorAll('a[href^="#"]')];
  const spy = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      anchors.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + en.target.id));
    });
  }, {rootMargin:'-45% 0px -50% 0px'});
  document.querySelectorAll('section[id]').forEach(s => spy.observe(s));

  const rev = new IntersectionObserver(entries => {
    entries.forEach(en => { if (en.isIntersecting){ en.target.classList.add('in'); rev.unobserve(en.target); } });
  }, {rootMargin:'0px 0px -8% 0px'});
  document.querySelectorAll('.section .wrap > *, .hero-copy, .demo').forEach((el,i) => {
    el.classList.add('reveal');
    el.style.transitionDelay = Math.min(i * 40, 240) + 'ms';
    rev.observe(el);
  });
})();

/* ─────────────────────────── weapon cards ─────────────────────────── */
(function cards(){
  const host = document.getElementById('weaponCards');
  host.innerHTML = WEAPONS.map(w => `
    <article class="card">
      <div class="card-top">
        <span class="msym ico">${w.ico}</span>
        <h3>${w.name}</h3>
        <span class="key">${w.key}</span>
      </div>
      <p>${w.text}</p>
      <span class="use">${w.use}</span>
    </article>`).join('');
})();

/* ─────────────────────────── playground ─────────────────────────── */
(function playground(){
  const view = document.getElementById('playground');
  if (!view) return;
  const W = view.width, H = view.height;
  const vctx = view.getContext('2d');

  const make = () => { const c = document.createElement('canvas'); c.width = W; c.height = H; return c; };
  const pristine = make(), world = make();
  const pctx = pristine.getContext('2d'), wctx = world.getContext('2d');

  const rnd = (a,b) => a + Math.random() * (b - a);
  const pick = arr => arr[(Math.random() * arr.length) | 0];

  /* --- mock desktop ------------------------------------------------ */
  function buildDesktop(ctx){
    const g = ctx.createLinearGradient(0,0,0,H);
    g.addColorStop(0,'#1d3f6e'); g.addColorStop(1,'#4a7fb5');
    ctx.fillStyle = g; ctx.fillRect(0,0,W,H);

    const wins = [[60,58,380,230],[470,110,370,250],[150,330,330,180]];
    wins.forEach(([x,y,w,h],i) => {
      ctx.fillStyle = 'rgba(0,0,0,.28)';
      ctx.fillRect(x+7,y+9,w,h);
      ctx.fillStyle = '#f6f7fa'; ctx.fillRect(x,y,w,h);
      ctx.fillStyle = '#2f3543'; ctx.fillRect(x,y,w,30);
      ['#ff5f57','#febc2e','#28c840'].forEach((c,j) => {
        ctx.fillStyle = c; ctx.beginPath(); ctx.arc(x+16+j*16,y+15,5,0,7); ctx.fill();
      });
      ctx.fillStyle = '#cfd5e0';
      for (let r = 0; r < 5; r++) ctx.fillRect(x+18,y+50+r*26,w-60-r*22,10);
      ctx.fillStyle = 'rgba(255,255,255,.55)';
      ctx.font = '600 13px Segoe UI, system-ui'; ctx.fillText(`window ${i+1}`, x+72, y+20);
    });
    ctx.fillStyle = '#12141b'; ctx.fillRect(0,H-42,W,42);
    for (let i = 0; i < 7; i++){
      ctx.fillStyle = '#39404f';
      ctx.fillRect(22+i*44,H-33,30,24);
    }
  }
  buildDesktop(pctx);
  wctx.drawImage(pristine,0,0);

  /* --- particles --------------------------------------------------- */
  const bits = [];
  function spawn(o){ if (bits.length < 900) bits.push(o); }
  function glow(x,y,vx,vy,life,size,col){ spawn({x,y,vx,vy,life,max:life,size,col,t:'g',grav:200,drag:2.2}); }
  function chunk(x,y,vx,vy,life,size,col){ spawn({x,y,vx,vy,life,max:life,size,col,t:'c',grav:1100,drag:.4,rot:rnd(0,6),vr:rnd(-12,12)}); }
  function puff(x,y,vx,vy,life,size){ spawn({x,y,vx,vy,life,max:life,size,col:'50,45,42',t:'s',grav:-30,drag:1.1,grow:2.6}); }

  function sparks(x,y,n,spd=340,col='255,208,130'){
    for (let i=0;i<n;i++){ const a=rnd(0,6.28), s=rnd(50,spd);
      glow(x,y,Math.cos(a)*s,Math.sin(a)*s,rnd(.2,.55),rnd(2,4.5),col); }
  }
  function debris(x,y,n,spd=460){
    for (let i=0;i<n;i++){ const a=rnd(0,6.28), s=rnd(90,spd);
      chunk(x,y,Math.cos(a)*s,Math.sin(a)*s,rnd(.5,1.1),rnd(2,5.5),pick(['58,58,66','82,82,92','200,220,240'])); }
  }

  /* --- decals ------------------------------------------------------ */
  function jag(ctx,x,y,ang,len,steps=4,wob=.2){
    ctx.moveTo(x,y);
    for (let i=0;i<steps;i++){ ang += rnd(-wob,wob); x += Math.cos(ang)*len/steps; y += Math.sin(ang)*len/steps; ctx.lineTo(x,y); }
    return [x,y];
  }

  function crack(x,y,R){
    const arms = 12, rays = [];
    for (let i=0;i<arms;i++){
      const a = i*6.283/arms + rnd(-.1,.1), len = R*rnd(.6,1);
      const pts = [[x,y]]; let cx=x, cy=y, ca=a;
      for (let s=0;s<4;s++){ ca += rnd(-.16,.16); cx += Math.cos(ca)*len/4; cy += Math.sin(ca)*len/4; pts.push([cx,cy]); }
      rays.push(pts);
    }
    // faint facets between neighbouring rays
    wctx.save();
    rays.forEach((p,i) => {
      const q = rays[(i+1)%arms];
      wctx.beginPath(); wctx.moveTo(x,y);
      p.slice(1).forEach(([a,b]) => wctx.lineTo(a,b));
      for (let k=q.length-1;k>0;k--) wctx.lineTo(q[k][0],q[k][1]);
      wctx.closePath();
      wctx.fillStyle = Math.random() < .5 ? 'rgba(0,0,0,.13)' : 'rgba(255,255,255,.10)';
      wctx.fill();
    });
    // concentric rings tie the rays together — the spiderweb signature
    [.36,.64,.88].forEach(f => {
      wctx.beginPath();
      rays.forEach((p,i) => {
        const idx = Math.min(p.length-1, Math.max(1, Math.round(f*(p.length-1))));
        const [a,b] = p[idx]; i ? wctx.lineTo(a,b) : wctx.moveTo(a,b);
      });
      wctx.closePath(); wctx.strokeStyle='rgba(16,15,18,.62)'; wctx.lineWidth=1.6; wctx.stroke();
    });
    wctx.beginPath();
    rays.forEach(p => { wctx.moveTo(p[0][0],p[0][1]); p.slice(1).forEach(([a,b]) => wctx.lineTo(a,b)); });
    wctx.strokeStyle='rgba(14,13,16,.9)'; wctx.lineWidth=2; wctx.stroke();
    wctx.beginPath(); wctx.arc(x,y,R*.13,0,7); wctx.fillStyle='#0a0a0c'; wctx.fill();
    wctx.restore();
  }

  function hole(x,y,r){
    wctx.beginPath(); wctx.arc(x,y,r*1.5,0,7); wctx.fillStyle='rgba(40,36,36,.4)'; wctx.fill();
    wctx.beginPath();
    for (let i=0;i<11;i++){ const a=i*6.283/11, rr=r*rnd(.72,1);
      i ? wctx.lineTo(x+Math.cos(a)*rr,y+Math.sin(a)*rr) : wctx.moveTo(x+Math.cos(a)*rr,y+Math.sin(a)*rr); }
    wctx.closePath(); wctx.fillStyle='#08080a'; wctx.fill();
    wctx.beginPath();
    for (let i=0;i<4;i++){ jag(wctx,x,y,rnd(0,6.28),r*rnd(1.2,2),3,.4); }
    wctx.strokeStyle='rgba(18,17,20,.6)'; wctx.lineWidth=1; wctx.stroke();
  }

  function slash(x0,y0,x1,y1){
    const dx=x1-x0, dy=y1-y0, len=Math.hypot(dx,dy);
    if (len < 8) return;
    const ux=dx/len, uy=dy/len, px=-uy, py=ux, half=rnd(3.5,5.5);
    const top=[], bot=[], steps=Math.max(6,(len/9)|0);
    for (let i=0;i<=steps;i++){
      const t=i/steps, w=half*Math.pow(Math.sin(Math.PI*t),.7)*rnd(.85,1.15);
      const cx=x0+dx*t, cy=y0+dy*t;
      top.push([cx+px*w,cy+py*w]); bot.push([cx-px*w,cy-py*w]);
    }
    wctx.beginPath(); wctx.moveTo(top[0][0],top[0][1]);
    top.forEach(([a,b])=>wctx.lineTo(a,b));
    for (let i=bot.length-1;i>=0;i--) wctx.lineTo(bot[i][0],bot[i][1]);
    wctx.closePath(); wctx.fillStyle='#0b0a0d'; wctx.fill();
    wctx.beginPath(); wctx.moveTo(top[0][0],top[0][1]-1);
    top.forEach(([a,b])=>wctx.lineTo(a,b-1));
    wctx.strokeStyle='rgba(246,250,255,.42)'; wctx.lineWidth=1; wctx.stroke();
    for (let i=0;i<len/16;i++){
      const t=rnd(.15,.85), s=Math.random()<.5?1:-1;
      const cx=x0+dx*t+px*half*s, cy=y0+dy*t+py*half*s;
      wctx.beginPath(); wctx.moveTo(cx,cy);
      wctx.lineTo(cx+rnd(-8,8), cy+s*rnd(5,15));
      wctx.strokeStyle='rgba(18,17,20,.55)'; wctx.lineWidth=1; wctx.stroke();
    }
    sparks((x0+x1)/2,(y0+y1)/2,14,300);
  }

  function scorch(x,y,r,a){
    const g = wctx.createRadialGradient(x,y,0,x,y,r);
    g.addColorStop(0,`rgba(16,12,11,${a})`);
    g.addColorStop(.55,`rgba(16,12,11,${a*.7})`);
    g.addColorStop(1,'rgba(16,12,11,0)');
    wctx.fillStyle=g; wctx.beginPath(); wctx.arc(x,y,r,0,7); wctx.fill();
  }

  function boom(x,y){
    for (let i=0;i<7;i++) scorch(x+rnd(-30,30), y+rnd(-30,30), rnd(55,95), .5);
    for (let i=0;i<12;i++){
      const a=rnd(0,6.28), d=rnd(40,150);
      scorch(x+Math.cos(a)*d, y+Math.sin(a)*d, rnd(18,42), .3);
    }
    crack(x,y,110);
    for (let i=0;i<14;i++){ const a=rnd(0,6.28), d=rnd(30,170); hole(x+Math.cos(a)*d,y+Math.sin(a)*d,rnd(4,9)); }
    for (let i=0;i<60;i++){
      const a=rnd(0,6.28), s=140+560*Math.sqrt(Math.random());
      glow(x,y,Math.cos(a)*s,Math.sin(a)*s,rnd(.3,.8),rnd(10,24),'255,168,56');
    }
    debris(x,y,34,900); sparks(x,y,30,700);
    for (let i=0;i<16;i++){ const a=rnd(0,6.28), s=rnd(20,170);
      puff(x,y,Math.cos(a)*s,Math.sin(a)*s,rnd(1,2.2),rnd(16,30)); }
    waves.push({x,y,t:0});
    shake(18); flash = 1;
  }

  /* --- state ------------------------------------------------------- */
  let tool='hammer', down=false, last=null, dragFrom=null, dragTo=null, hue=0;
  let trauma=0, flash=0; const waves=[];
  const shake = n => trauma = Math.min(20, trauma + n);

  const TOOLS = [
    {id:'hammer', ico:'carpenter', label:'Hammer'},
    {id:'katana', ico:'swords', label:'Katana'},
    {id:'gun',    ico:'scatter_plot', label:'Shotgun'},
    {id:'grenade',ico:'bomb', label:'Grenade'},
    {id:'flame',  ico:'local_fire_department', label:'Flame'},
    {id:'paint',  ico:'brush', label:'Paint'},
  ];
  const bar = document.getElementById('demoTools');
  bar.innerHTML = TOOLS.map(t =>
    `<button class="tool-btn${t.id==='hammer'?' on':''}" data-t="${t.id}"><span class="msym ic">${t.ico}</span>${t.label}</button>`
  ).join('') + `<button class="tool-btn reset" data-t="wash"><span class="msym ic">cleaning_services</span>Wash it clean</button>`;

  bar.addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.t === 'wash'){
      wctx.drawImage(pristine,0,0); bits.length=0; waves.length=0; return;
    }
    tool = b.dataset.t;
    bar.querySelectorAll('.tool-btn').forEach(x => x.classList.toggle('on', x === b));
  });

  /* --- input ------------------------------------------------------- */
  const hint = document.getElementById('demoHint');
  const at = e => {
    const r = view.getBoundingClientRect();
    return [ (e.clientX - r.left) * (W / r.width), (e.clientY - r.top) * (H / r.height) ];
  };

  function strike(x,y){
    if (tool==='hammer'){ crack(x,y,rnd(46,74)); debris(x,y,14); sparks(x,y,8,220); shake(9); }
    else if (tool==='gun'){
      for (let i=0;i<7;i++){ const a=rnd(0,6.28), d=rnd(0,40); hole(x+Math.cos(a)*d,y+Math.sin(a)*d,rnd(6,11)); }
      sparks(x,y,18,420); debris(x,y,7); shake(6);
      glow(x,y,0,0,.09,40,'255,236,190');
    }
    else if (tool==='grenade'){ boom(x,y); }
  }

  function drag(x,y){
    if (!last) { last = [x,y]; return; }
    const [lx,ly] = last, d = Math.hypot(x-lx,y-ly), steps = Math.max(1,(d/6)|0);
    for (let i=1;i<=steps;i++){
      const t=i/steps, cx=lx+(x-lx)*t, cy=ly+(y-ly)*t;
      if (tool==='flame'){
        scorch(cx,cy,rnd(20,34),.32);
        for (let k=0;k<2;k++){ const a=rnd(0,6.28), s=rnd(10,90);
          glow(cx,cy,Math.cos(a)*s,Math.sin(a)*s-rnd(40,120),rnd(.28,.6),rnd(9,18),'255,146,42'); }
        if (Math.random()<.08) puff(cx,cy,rnd(-20,20),-rnd(30,80),rnd(.7,1.4),rnd(10,18));
      } else if (tool==='paint'){
        hue = (hue + 1.1) % 360;
        wctx.beginPath(); wctx.arc(cx,cy,13,0,7);
        wctx.fillStyle = `hsl(${hue} 88% 56%)`; wctx.fill();
      }
    }
    last = [x,y];
  }

  view.addEventListener('pointerdown', e => {
    e.preventDefault();
    try { view.setPointerCapture(e.pointerId); } catch { /* not all pointers can be captured */ }
    hint.classList.add('gone');
    const [x,y] = at(e); down = true; last = [x,y];
    if (tool==='katana') dragFrom = [x,y]; else strike(x,y);
  });
  view.addEventListener('pointermove', e => {
    if (!down) return;
    const [x,y] = at(e);
    if (tool==='katana'){ dragTo = [x,y]; return; }
    if (tool==='flame' || tool==='paint') drag(x,y);
    else if (tool==='gun' && Math.random()<.28) strike(x,y);
  });
  addEventListener('pointerup', e => {
    if (!down) return;
    down = false;
    if (tool==='katana' && dragFrom){
      const [x,y] = at(e);
      const far = Math.hypot(x-dragFrom[0], y-dragFrom[1]) > 30;
      if (far) slash(dragFrom[0],dragFrom[1],x,y);
      else { const a=rnd(-.7,-.4), L=rnd(70,120);
             slash(x-Math.cos(a)*L, y-Math.sin(a)*L, x+Math.cos(a)*L, y+Math.sin(a)*L); }
      shake(7);
    }
    dragFrom = dragTo = null; last = null;
  });
  view.addEventListener('contextmenu', e => e.preventDefault());

  /* --- loop -------------------------------------------------------- */
  let prev = performance.now();
  function frame(now){
    const dt = Math.min(.05,(now - prev)/1000); prev = now;

    for (let i=bits.length-1;i>=0;i--){
      const p = bits[i];
      p.life -= dt;
      if (p.life <= 0){ bits.splice(i,1); continue; }
      const damp = Math.max(0, 1 - p.drag*dt);
      p.vx *= damp; p.vy *= damp; p.vy += p.grav*dt;
      p.x += p.vx*dt; p.y += p.vy*dt;
      if (p.vr) p.rot += p.vr*dt;
    }
    trauma = Math.max(0, trauma - dt*trauma*7 - dt*2);
    flash = Math.max(0, flash - dt*7);
    for (let i=waves.length-1;i>=0;i--){ waves[i].t += dt/.55; if (waves[i].t>=1) waves.splice(i,1); }

    const ox = trauma ? rnd(-trauma,trauma) : 0, oy = trauma ? rnd(-trauma,trauma) : 0;
    vctx.setTransform(1,0,0,1,0,0);
    if (trauma){ vctx.fillStyle='#000'; vctx.fillRect(0,0,W,H); }
    vctx.drawImage(world, ox, oy);

    vctx.save(); vctx.translate(ox,oy);
    vctx.globalCompositeOperation='lighter';
    bits.forEach(p => {
      if (p.t !== 'g') return;
      const k = 1 - p.life/p.max, f = Math.pow(1-k,.7);
      vctx.fillStyle = `rgba(${p.col},${f})`;
      vctx.beginPath(); vctx.arc(p.x,p.y,p.size*(1-k*.75),0,7); vctx.fill();
    });
    waves.forEach(w => {
      const r = 26 + w.t*300, f = Math.pow(1-w.t,1.6);
      vctx.strokeStyle = `rgba(255,214,150,${f*.75})`; vctx.lineWidth = 10*f;
      vctx.beginPath(); vctx.arc(w.x,w.y,r,0,7); vctx.stroke();
    });
    vctx.globalCompositeOperation='source-over';
    bits.forEach(p => {
      const k = 1 - p.life/p.max;
      if (p.t === 'c'){
        vctx.save(); vctx.translate(p.x,p.y); vctx.rotate(p.rot);
        vctx.fillStyle = `rgba(${p.col},${1-k*.4})`;
        vctx.fillRect(-p.size,-p.size,p.size*2,p.size*2); vctx.restore();
      } else if (p.t === 's'){
        vctx.fillStyle = `rgba(${p.col},${.34*(1-k)})`;
        vctx.beginPath(); vctx.arc(p.x,p.y,p.size*(1+k*p.grow),0,7); vctx.fill();
      }
    });
    if (dragFrom && dragTo && tool==='katana'){
      vctx.strokeStyle='rgba(255,250,240,.9)'; vctx.lineWidth=2;
      vctx.beginPath(); vctx.moveTo(dragFrom[0],dragFrom[1]); vctx.lineTo(dragTo[0],dragTo[1]); vctx.stroke();
    }
    vctx.restore();

    if (flash > 0){
      vctx.globalCompositeOperation='lighter';
      vctx.fillStyle = `rgba(255,228,190,${.30*flash*flash})`;
      vctx.fillRect(0,0,W,H);
      vctx.globalCompositeOperation='source-over';
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
