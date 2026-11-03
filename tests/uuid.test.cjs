const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {webcrypto}=require('node:crypto');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/workspace.js'),'utf8');
const definition=source.slice(source.indexOf('const uid ='),source.indexOf('const clone ='));
const generator=crypto=>vm.runInNewContext(definition+'\nuid;',{crypto});
test('uses native randomUUID when available with its crypto receiver',()=>{
 const crypto={randomUUID(){assert.equal(this,crypto);return 'native-id';}};
 assert.equal(generator(crypto)(),'native-id');
});
test('HTTP fallback creates independent RFC 4122 version 4 IDs without randomUUID',()=>{
 const uid=generator({getRandomValues:array=>webcrypto.getRandomValues(array)});
 const ids=Array.from({length:5000},()=>uid());
 assert.ok(ids.every(id=>/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id)));
 assert.equal(new Set(ids).size,ids.length);
});
