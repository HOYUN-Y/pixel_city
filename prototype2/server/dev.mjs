import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createGuide,httpHandler} from './guide.mjs';
const root=path.resolve(fileURLToPath(new URL('../',import.meta.url)));
const {places}=JSON.parse(await readFile(path.join(root,'assets/city_pilot/places.json')));
const guide=httpHandler(createGuide({places}));
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.woff2':'font/woff2'};
http.createServer(async(req,res)=>{
  const url=new URL(req.url,'http://localhost');if(url.pathname==='/api/guide')return guide(req,res);
  const name=url.pathname==='/'?'/web/pilot/index.html':decodeURIComponent(url.pathname);
  const file=path.resolve(root,'.'+name);if(!file.startsWith(root+path.sep)||!/^\/(web\/pilot|assets\/city_pilot|assets\/city_dense)\//.test(name)){res.writeHead(404).end();return;}
  try{let body=await readFile(file);
    if(url.pathname==='/')body=body.toString().replace('src="app.js"','src="/web/pilot/beta-app.js"').replace('href="style.css"','href="/web/pilot/style.css"').replace('<body>','<body data-city-base="/assets/city_pilot/">').replace(/  <details id="inspection">[\s\S]*?<\/details>\n/,'').replace(/  <div id="route-bar"[\s\S]*?<\/dialog>\n/,'');
    if(url.pathname==='/'&&url.searchParams.get('dense')==='1')body=body.replace('data-city-base="/assets/city_pilot/"','data-city-base="/assets/city_dense/"');
    res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');res.end(body);
  }catch{res.writeHead(404).end();}
}).listen(8768,'127.0.0.1',()=>console.log('http://127.0.0.1:8768/'));
