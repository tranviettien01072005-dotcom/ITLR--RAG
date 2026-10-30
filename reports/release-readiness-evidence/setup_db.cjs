const fs=require('node:fs'),crypto=require('node:crypto');
const {Pool}=require('/home/o/ITLR--RAG/web/node_modules/pg');
const {spawnSync}=require('node:child_process');
(async()=>{
 const admin=new Pool({host:'/tmp/itlr-release/pg-socket',port:15432,user:'o',database:'postgres'});
 const password=crypto.randomBytes(24).toString('hex');
 const literal=(await admin.query('SELECT quote_literal($1) AS q',[password])).rows[0].q;
 await admin.query('CREATE ROLE itlr_fixture LOGIN PASSWORD '+literal);
 await admin.query('CREATE DATABASE itlr_fixture OWNER itlr_fixture');
 await admin.end();
 const env={...process.env,DATABASE_URL:`postgresql://itlr_fixture:${password}@127.0.0.1:15432/itlr_fixture`,JWT_SECRET:crypto.randomBytes(32).toString('hex'),ADMIN_PASSCODE:crypto.randomBytes(24).toString('hex'),PORT:'18030',APP_ORIGIN:'http://127.0.0.1:18030',RECOMMENDER_URL:'http://127.0.0.1:18031',NODE_ENV:'test',USE_OLLAMA:'0',SMTP_USER:'',SMTP_PASS:'',SMTP_HOST:''};
 delete env.DEEPSEEK_API_KEY;delete env.OPENAI_API_KEY;
 fs.writeFileSync('/tmp/itlr-release/private-env.json',JSON.stringify(env),{mode:0o600});
 const pg=new Pool({connectionString:env.DATABASE_URL});
 for(let i=1;i<=2;i++){
  const r=spawnSync('/home/o/ITLR--RAG/web/node_modules/.bin/tsx',['src/db/migrate.ts'],{cwd:'/home/o/ITLR--RAG/web',env,encoding:'utf8'});
  fs.writeFileSync(`/tmp/itlr-release/migration-${i}.log`,r.stdout+r.stderr);
  if(r.status!==0) throw new Error('migration '+i+' failed; see log');
 }
 const fixtures=[[700001,'Python introduction fixture','https://docs.python.org/3/tutorial/introduction.html'],[700002,'Python modules fixture','https://docs.python.org/3/tutorial/modules.html'],[700003,'Python project CSV fixture','https://docs.python.org/3/library/csv.html']];
 for(const [id,title,link] of fixtures)await pg.query('INSERT INTO courses(item_id,title,type,level,description,category,topics,platform,link,origin) VALUES($1,$2,\'documentation\',\'beginner\',\'Isolated integration fixture\',\'programming\',\'python\',\'fixture\',$3,\'crawl:fixture\')',[id,title,link]);
 const tables=(await pg.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows;
 fs.writeFileSync('/tmp/itlr-release/migration-result.json',JSON.stringify({migrationRuns:2,fixtureCourses:3,tables:tables.map(r=>r.tablename)},null,2));
 await pg.end();console.log('PASS two migrations; three fixture courses; private environment written mode 0600.');
})().catch(e=>{console.error(e.message);process.exitCode=1});
