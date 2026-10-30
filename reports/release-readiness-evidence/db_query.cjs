const fs=require('node:fs');
const {Pool}=require('/home/o/ITLR--RAG/web/node_modules/pg');
(async()=>{
 const env=JSON.parse(fs.readFileSync('/tmp/itlr-release/private-env.json','utf8'));
 const pg=new Pool({connectionString:env.DATABASE_URL});
 let input='';for await(const c of process.stdin)input+=c;
 const {sql,params=[]}=JSON.parse(input);
 console.log(JSON.stringify((await pg.query(sql,params)).rows));await pg.end();
})().catch(e=>{console.error(e.message);process.exitCode=1});
