import {createHmac, randomUUID} from 'node:crypto';

// Never expire or recreate the lifetime ledger on a request/deployment.
export const LEDGER='pixel-city:guide:lifetime:v1';
export const RESERVE_MICRO=10000, LIMIT_MICRO=1000000;
export const RESERVE_LUA=`
if redis.call('EXISTS', KEYS[1]) == 0 then return 'uninitialized' end
if redis.call('HGET', KEYS[1], 'blocked') == '1' then return 'blocked' end
local used=tonumber(redis.call('HGET', KEYS[1], 'used'))
if not used then return 'invalid' end
if used + tonumber(ARGV[2]) > tonumber(ARGV[3]) then return 'budget' end
if redis.call('HLEN', KEYS[2]) >= 2 then return 'busy' end
if tonumber(redis.call('GET', KEYS[3]) or '0') >= 3 then return 'rate' end
if tonumber(redis.call('GET', KEYS[4]) or '0') >= 20 then return 'rate' end
redis.call('INCR', KEYS[3]); redis.call('EXPIRE', KEYS[3], 120)
redis.call('INCR', KEYS[4]); redis.call('EXPIRE', KEYS[4], 172800)
redis.call('HINCRBY', KEYS[1], 'used', ARGV[2])
redis.call('HSET', KEYS[2], ARGV[1], ARGV[2])
return 'ok'`;
export const SETTLE_LUA=`
local reserved=tonumber(redis.call('HGET', KEYS[2], ARGV[1]))
if not reserved or redis.call('EXISTS', KEYS[1]) == 0 then return 'missing' end
local actual=tonumber(ARGV[2])
if not actual or actual < 0 or actual > reserved then
  redis.call('HSET', KEYS[1], 'blocked', '1'); return 'blocked'
end
redis.call('HINCRBY', KEYS[1], 'used', actual-reserved)
redis.call('HDEL', KEYS[2], ARGV[1])
redis.call('HINCRBY', KEYS[1], 'completed', 1)
return 'ok'`;

export function redisBudget(env=process.env, fetcher=fetch){
  const url=env.UPSTASH_REDIS_REST_URL||env.KV_REST_API_URL,token=env.UPSTASH_REDIS_REST_TOKEN||env.KV_REST_API_TOKEN,salt=env.GUIDE_IP_HASH_SALT;
  if(!url||!token||!salt||salt.length<24||!/^https:\/\/[a-z0-9-]+\.upstash\.io\/?$/.test(url))return null;
  async function command(args){
    const r=await fetcher(url,{method:'POST',redirect:'error',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify(args),signal:AbortSignal.timeout(5000)});
    if(!r.ok)throw Error('budget unavailable');const v=await r.json();if(v.error)throw Error('budget unavailable');return v.result;
  }
  return {
    async ready(){const v=await command(['HMGET',LEDGER,'used','blocked']);return Array.isArray(v)&&v[0]!==null&&Number(v[0])+RESERVE_MICRO<=LIMIT_MICRO&&v[1]!=='1';},
    async reserve(ip){
      const now=Date.now(),id=randomUUID(),hash=createHmac('sha256',salt).update(ip).digest('hex');
      const result=await command(['EVAL',RESERVE_LUA,4,LEDGER,LEDGER+':active',`${LEDGER}:minute:${Math.floor(now/60000)}:${hash}`,`${LEDGER}:day:${Math.floor(now/86400000)}:${hash}`,id,RESERVE_MICRO,LIMIT_MICRO]);
      if(result!=='ok')throw Error('budget '+result);return id;
    },
    async settle(id,micro){const result=await command(['EVAL',SETTLE_LUA,2,LEDGER,LEDGER+':active',id,micro]);if(result!=='ok')throw Error('billing blocked');},
    async block(){await command(['HSET',LEDGER,'blocked','1']);}
  };
}
