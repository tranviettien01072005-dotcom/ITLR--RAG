const http=require('node:http');
const item={item_id:700001,title:'Python introduction fixture',description:'Isolated integration fixture',topics:'python',type:'documentation',category:'programming',instructor:'',platform:'fixture',link:'https://docs.python.org/3/tutorial/introduction.html',level:'beginner',origin:'crawl:fixture',score:1};
const final={type:'final',response:'Fixture answer: Python introduction [item_id:700001]',sources:[item],recommendations:[item],intent:'learning',generation_mode:'fixture',citation_validation:{valid:true}};
const server=http.createServer(async(req,res)=>{
 let body='';for await(const c of req)body+=c;
 let parsed={};try{parsed=JSON.parse(body||'{}')}catch{}
 const json=value=>{res.setHeader('content-type','application/json');res.end(JSON.stringify(value))};
 if(req.url==='/api/search')return json({results:[item],display:'Fixture search',note:'explicit fixture',corrected:false});
 if(req.url==='/api/suggested')return json({prompts:['Explain fixture Python'],welcome:'Fixture welcome'});
 if(req.url==='/api/personas'){res.statusCode=503;return json({detail:'CF fixture unavailable'})}
 if(req.url==='/api/chat')return json(final);
 if(req.url==='/api/chat/stream'){
  res.writeHead(200,{'content-type':'text/event-stream'});
  const events=[{type:'sources',sources:[item]},{type:'text',text:'Fixture answer'},final,{type:'done'}];
  if(parsed.message==='fixture-missing-done')events.pop();
  for(const e of events)res.write('data: '+JSON.stringify(e)+'\n\n');
  return res.end();
 }
 res.statusCode=404;json({detail:'fixture route absent'});
});
server.listen(18031,'127.0.0.1',()=>console.log('Explicit upstream fixture listening18031'));
process.on('SIGTERM',()=>server.close());
