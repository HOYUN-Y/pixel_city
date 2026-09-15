// Paid model calls: none. Uses isolated, expiring keys; never changes the lifetime ledger.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {RESERVE_LUA,SETTLE_LUA} from '../server/budget.mjs';
const url=process.env.KV_REST_API_URL||process.env.UPSTASH_REDIS_REST_URL;
const token=process.env.KV_REST_API_TOKEN||process.env.UPSTASH_REDIS_REST_TOKEN;
if(!url||!token)throw Error('Redis credentials required');
async function command(args){const r=await fetch(url,{method:'POST',redirect:'error',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify(args),signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error('Redis HTTP error');const d=await r.json();if(d.error)throw Error('Redis command failed');return d.result;}
const prefix='pixel-city:test:'+randomUUID(),ledger=prefix+':ledger',active=prefix+':active';
const keys=new Set([ledger,active]);
async function reserve(id,ip='one'){
  const minute=prefix+':minute:'+ip,day=prefix+':day:'+ip;keys.add(minute);keys.add(day);
  return command(['EVAL',RESERVE_LUA,4,ledger,active,minute,day,id,10000,1000000]);
}
const settle=(id,cost)=>command(['EVAL',SETTLE_LUA,2,ledger,active,id,cost]);
try{
  assert.equal(await reserve('missing'),'uninitialized');
  await command(['HSET',ledger,'used',0,'blocked',0]);await command(['EXPIRE',ledger,300]);
  const result=await Promise.all(Array.from({length:10},(_,i)=>reserve('c'+i,'ip'+i)));
  assert.equal(result.filter(x=>x==='ok').length,2);assert.equal(result.filter(x=>x==='busy').length,8);
  await command(['EXPIRE',active,300]);
  for(let i=0;i<10;i++)if(result[i]==='ok')assert.equal(await settle('c'+i,0),'ok');
  assert.equal(await command(['HGET',ledger,'used']),'0');
  for(let i=0;i<3;i++){assert.equal(await reserve('r'+i),'ok');assert.equal(await settle('r'+i,0),'ok');}
  assert.equal(await reserve('rate'),'rate');
  await command(['SET',prefix+':minute:one',0,'EX',300]);await command(['SET',prefix+':day:one',20,'EX',300]);
  assert.equal(await reserve('day'),'rate');
  await command(['HSET',ledger,'used',995000]);assert.equal(await reserve('budget','fresh'),'budget');
  await command(['HSET',ledger,'used',0]);assert.equal(await reserve('unknown','fresh'),'ok');
  assert.equal(await settle('unknown',-1),'blocked');assert.equal(await reserve('after','another'),'blocked');
  console.log(JSON.stringify({passed:true,concurrentRequests:10,accepted:2,minuteLimit:3,dayLimit:20,lifetimeCapUSD:1,unknownBillingFailsClosed:true,paidCalls:0}));
}finally{await command(['DEL',...keys]);}
