// Offline DOM-contract execution of the real dashboard JavaScript. No browser/network/account.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

function fixture(options = {}) {
  const nodes = new Map();
  const html = fs.readFileSync(path.join(root, 'public/index.html'), 'utf8');
  for (const match of html.matchAll(/\bid="([^"]+)"/g)) {
    const classes = new Set();
    nodes.set(match[1], {
      innerHTML: '', textContent: '', value: '', disabled: false, dataset: {},
      addEventListener() {},
      classList: { add: (v) => classes.add(v), remove: (v) => classes.delete(v),
        toggle: (v, yes) => yes ? classes.add(v) : classes.delete(v), contains: (v) => classes.has(v) },
    });
  }
  nodes.get('minutes').value = '20';
  nodes.get('capture-source').value = 'manual';
  const requests = [], history = [], storage = new Map(), events = new Map();
  let uuid = 0;
  const context = vm.createContext({
    URL, console, setTimeout: () => 1, clearTimeout() {}, setInterval() {},
    crypto: { randomUUID: () => `test-request-${++uuid}` },
    window: { location: { href: options.url || 'https://between.example/' },
      history: { replaceState: (...args) => history.push(args) } },
    localStorage: { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    document: { getElementById: (id) => nodes.get(id) || null,
      addEventListener: (type, fn) => events.set(type, fn),
      body: { addEventListener() {} }, querySelector: () => null, querySelectorAll: () => [], activeElement: null },
    fetch: async (url, init) => {
      requests.push({ url, init });
      if (options.fetch) return options.fetch(url, init);
      const data = url === '/api/ask' ? {answer: 'Try your next recorded step.'} : {};
      return { status: 200, ok: true, json: async () => data };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(root, 'public/app.js'), 'utf8'), context);
  return { nodes, context, requests, history, events, storage,
    run: (code) => vm.runInContext(code, context) };
}

async function run() {
  let checks = 0;
  {
    const task = {id:1,title:'Synthetic reading',status:'open',category:'important',duration_minutes:30,logged_minutes:0};
    const responses = {
      '/api/state': {tasks:[task],inbox:[],stats:{}},
      '/api/free-time': {source:'Google Calendar',free_now_minutes:20,gaps:[]},
      '/api/plan?minutes=20': {plan:[{task_id:1,title:task.title,kind:'progress',minutes:20}],fits:0},
      '/api/questions': {questions:[{id:1,task_title:task.title,question:'When is it due?',field:'due'}]},
      '/api/today': {blocks:[{task_id:1,title:task.title,start:'10:00',end:'10:30',minutes:30,category:'important',reason:'Fits your free time.'}],unplaced:0},
      '/api/insights': {insights:[]},
    };
    const f = fixture({fetch:async (url) => {
      assert.ok(Object.hasOwn(responses,url), `Unexpected dashboard request: ${url}`);
      return {status:200,ok:true,json:async()=>responses[url]};
    }});
    await f.run('load()');
    assert.equal(f.nodes.get('status').textContent,'Connected');
    assert.equal(f.requests.length,6);
    assert.ok(f.nodes.get('tasks').innerHTML.includes(task.title));
    assert.ok(f.nodes.get('fits').innerHTML.includes(task.title));
    assert.ok(f.nodes.get('today').innerHTML.includes('Fits your free time.'));
    assert.ok(f.nodes.get('questions').innerHTML.includes('When is it due?'));
    assert.equal(f.nodes.get('pip-insights').classList.contains('hidden'),true);
    checks++;
  }
  {
    const f = fixture();
    f.nodes.delete('questions-card'); f.nodes.delete('questions');
    assert.doesNotThrow(() => f.run('renderQuestions()'));
    checks++;
  }
  {
    const f = fixture();
    f.run(`state.questions = [{id:1,question:'<img src=x onerror=alert(1)>',task_title:'A',field:'due'}]; renderQuestions()`);
    assert.ok(f.nodes.get('questions').innerHTML.includes('&lt;img'));
    assert.ok(!f.nodes.get('questions').innerHTML.includes('<img'));
    checks++;
  }
  {
    const f = fixture();
    const steps = [2,3,4].map((id) => ({id, title:'<b>Step</b>',status:'open',duration_minutes:30,logged_minutes:0}));
    const parent = {id:1,title:'Exam',status:'open',category:'important',steps,next_step_id:2,steps_done:0,remaining_minutes:90};
    f.run(`state.tasks = ${JSON.stringify([parent])}; renderTasks()`);
    const html = f.nodes.get('tasks').innerHTML;
    assert.ok(html.includes('Your next small step'));
    assert.ok(html.includes('View all 3 steps'));
    assert.ok(html.includes('data-log-open="2"'));
    assert.ok(!html.includes('data-log-open="3"'));
    assert.ok(html.includes('&lt;b&gt;Step'));
    checks++;
  }
  {
    const f = fixture();
    f.run(`state.tasks = [{id:1,title:'Learn pottery',status:'open',category:'important',quiet_filed:1}]; renderTasks()`);
    assert.ok(!f.nodes.get('tasks').innerHTML.includes('Learn pottery'));
    assert.ok(f.nodes.get('someday').innerHTML.includes('Learn pottery'));
    assert.equal(f.nodes.get('someday-card').classList.contains('hidden'), false);
    checks++;
  }
  {
    const f = fixture({url:'https://between.example/?token=test-only-token',
      fetch: async () => ({status:200,ok:true,json:async()=>({answer:'<b>Known fact</b>'})})});
    f.nodes.get('ask-question').value = 'Where should I start?';
    await f.run('askPip({preventDefault(){}})');
    assert.equal(f.nodes.get('pip-answer').textContent, '<b>Known fact</b>');
    assert.equal(f.nodes.get('pip-answer').innerHTML, '');
    assert.equal(f.nodes.get('ask-button').disabled, false);
    assert.equal(f.requests[0].init.headers['X-Life-Brain-Token'], 'test-only-token');
    assert.equal(f.history[0][2], '/');
    checks++;
  }
  {
    const f = fixture({fetch: async () => {throw new Error('Offline test');}});
    f.nodes.get('ask-question').value = 'Help me start';
    await f.run('askPip({preventDefault(){}})');
    assert.equal(f.nodes.get('pip-answer').textContent, 'Offline test');
    assert.equal(f.nodes.get('ask-button').disabled, false);
    checks++;
  }
  {
    let captures = 0;
    const f = fixture({fetch: async (url) => {
      if (url === '/api/capture' && ++captures === 1) throw new Error('Retry this synthetic capture');
      return {status:200,ok:true,json:async()=>({})};
    }});
    f.nodes.get('capture-text').value = 'Read chapter four';
    await f.run('addCapture({preventDefault(){}})');
    await f.run('addCapture({preventDefault(){}})');
    const bodies = f.requests.filter((r) => r.url === '/api/capture').map((r) => JSON.parse(r.init.body));
    assert.equal(bodies.length, 2);
    assert.equal(bodies[0].idempotency_key, bodies[1].idempotency_key);
    checks++;
  }
  return {checks, result:'PASS', note:'Synthetic DOM execution; not a visual browser rehearsal'};
}
module.exports = run;
if (require.main === module) run().then(console.log).catch((err) => {console.error(err);process.exitCode=1;});
