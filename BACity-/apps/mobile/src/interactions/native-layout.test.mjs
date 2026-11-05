import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { sheetTarget } from '../navigation/motion.ts';
test('sheet snaps honor direction, velocity and short content detents',()=>{
 assert.equal(sheetTarget(120,-900,[0,160,320]),0);
 assert.equal(sheetTarget(120,100,[0,160,320]),160);
 assert.equal(sheetTarget(230,900,[0,160,320]),320);
 assert.equal(sheetTarget(30,0,[0,0,140]),0);
});
test('native surfaces contain no raw text, including single-line JSX spaces',()=>{
 const files=['../map/MapScreen.tsx','../map/MapFilters.tsx','../components/sheets/AppSheet.tsx','../components/interactions/FeedbackComposer.tsx','../components/interactions/NavListCard.tsx','../components/interactions/ActionButton.tsx'];
 for(const file of files){const source=readFileSync(new URL(file,import.meta.url),'utf8'),ast=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),errors=[];
 function visit(node){if(ts.isJsxText(node)){const raw=node.getText(ast);if(raw.trim()||raw.length&&!raw.includes('\n')){let parent=node.parent;while(parent&&ts.isJsxFragment(parent))parent=parent.parent;const tag=parent&&ts.isJsxElement(parent)?parent.openingElement.tagName.getText(ast):'';if(!['Text','Animated.Text'].includes(tag))errors.push(`${ast.getLineAndCharacterOfPosition(node.pos).line+1}: ${JSON.stringify(raw)}`);}}ts.forEachChild(node,visit);}visit(ast);assert.deepEqual(errors,[],file);}
});
