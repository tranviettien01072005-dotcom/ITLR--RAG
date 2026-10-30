const fs=require('node:fs'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const {Pool}=require('/home/o/ITLR--RAG/web/node_modules/pg');
const base='/tmp/itlr-release',bin=base+'/pg-root/usr/lib/postgresql/18/bin/';
async function fingerprint(url){
 const db=new Pool({connectionString:url}),result={};
 const names=(await db.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows;
 for(const {tablename} of names){
  if(!/^[a-z_]+$/.test(tablename))throw Error('unexpected table identifier');
  const row=(await db.query(`SELECT count(*)::int AS count, COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]') AS data FROM "${tablename}" t`)).rows[0];
  result[tablename]={count:row.count,sha256:crypto.createHash('sha256').update(row.data).digest('hex')};
 }
 await db.end();return result;
}
(async()=>{
 const env=JSON.parse(fs.readFileSync(base+'/private-env.json','utf8')),url=new URL(env.DATABASE_URL);
 const toolenv={...env,LD_LIBRARY_PATH:base+'/pg-root/usr/lib/x86_64-linux-gnu',PGPASSWORD:decodeURIComponent(url.password)};
 function run(tool,args){const r=spawnSync(bin+tool,args,{env:toolenv,encoding:'utf8'});fs.appendFileSync(base+'/backup-restore.log',tool+' exit='+r.status+'\n'+r.stdout+r.stderr);if(r.status!==0)throw Error(tool+' failed; see log');}
 const before=await fingerprint(env.DATABASE_URL);
 run('pg_dump',['-h','127.0.0.1','-p','15432','-U','itlr_fixture','-d','itlr_fixture','-Fc','-f',base+'/fixture-backup.dump']);fs.chmodSync(base+'/fixture-backup.dump',0o600);
 const admin=new Pool({host:base+'/pg-socket',port:15432,user:'o',database:'postgres'});
 await admin.query('CREATE DATABASE itlr_restored OWNER itlr_fixture');await admin.end();
 run('pg_restore',['-h','127.0.0.1','-p','15432','-U','itlr_fixture','-d','itlr_restored','--exit-on-error',base+'/fixture-backup.dump']);
 url.pathname='/itlr_restored';const restored=await fingerprint(url.href);
 if(JSON.stringify(before)!==JSON.stringify(restored))throw Error('Restored table fingerprints differ');
 run('pg_ctl',['-D',base+'/pg-data','-m','fast','-w','stop']);
 run('pg_ctl',['-D',base+'/pg-data','-l',base+'/postgres.log','-w','start']);
 const restarted=await fingerprint(env.DATABASE_URL);
 if(JSON.stringify(before)!==JSON.stringify(restarted))throw Error('Restart table fingerprints differ');
 fs.writeFileSync(base+'/backup-restore-result.json',JSON.stringify({scope:'Isolated local logical database backup/restore within same PostgreSQL18 cluster; not production/PITR/host-loss recovery',backupBytes:fs.statSync(base+'/fixture-backup.dump').size,tableCount:Object.keys(before).length,allTableFingerprintsEqual:true,clusterRestartPreservedData:true,tables:before},null,2));
 console.log('PASS logical backup/restore: '+Object.keys(before).length+' table row counts and SHA256 fingerprints equal; cluster restart preserves all data.');
})().catch(e=>{console.error(e.message);process.exitCode=1});
