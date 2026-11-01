#!/usr/bin/env node
// HOST-ONLY structural admission probes. Not TypeSpec compiler, DPM, or Oreslang.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const load = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const typeSpec = fs.readFileSync(path.join(root, 'contracts/typespec/document.tsp'), 'utf8');
const guest = fs.readFileSync(path.join(root, 'src/orm_schema.ores'), 'utf8');
const tests = fs.readFileSync(path.join(root, 'tests/schema_diff.ores'), 'utf8');
const original = {
  json: load('contracts/json-schema/document-row.schema.json'),
  overlay: load('contracts/storage/document.storage.v1.json'),
  policy: load('contracts/peer-authority.v1.json')
};
const inspect = ({json, overlay, policy}) => {
  assert.equal(json.$schema, 'https://json-schema.org/draft/2020-12/schema');
  const row = json.$defs.DocumentRow;
  assert.equal(row.type, 'object');
  assert.equal(row.additionalProperties, false);
  assert.deepEqual(Object.keys(row.properties), ['workspace_id','id','title','note']);
  assert.deepEqual([...row.required].sort(), Object.keys(row.properties).sort());
  for (const col of ['workspace_id','id']) {
    assert.equal(row.properties[col].type,'string');
    assert.equal(row.properties[col].format,'uuid');
  }
  assert.equal(row.properties.title.type, 'string');
  assert.deepEqual(row.properties.note.anyOf, [{type:'string'},{type:'null'}]);
  assert.equal(overlay.schema,'ores.orm.storage-overlay/v1');
  assert.equal(overlay.status,'review_proposal_only');
  assert.equal(overlay.contractModel,'Ores.Orm.DocumentRow');
  assert.equal(overlay.table,'docs');
  assert.deepEqual(overlay.columns.map(x=>x.name), Object.keys(row.properties));
  assert.deepEqual(overlay.columns.map(x=>x.typeFamily), ['uuid','uuid','string','string']);
  assert.deepEqual(overlay.columns.map(x=>x.nullable), [false,false,false,true]);
  assert.deepEqual(overlay.primaryKey, ['workspace_id','id']);
  assert.equal(overlay.tenantKey, 'workspace_id');
  for (const x of ['defaults','constraints','indexes','foreign_keys','rls_policies','grants','extensions','generated_expressions','collations']) {
    assert.ok(overlay.manualReviewRequired.includes(x), 'missing unresolved DB semantics '+x);
  }
  const m = overlay.migrationPolicy;
  assert.equal(m.plannerAndApplier, 'declarative-migrations');
  assert.equal(m.allowDirectOrmApply, false);
  assert.equal(m.allowAutoDropOrRename, false);
  assert.equal(m.requireExactObservedCatalog, true);
  assert.equal(m.requireIndependentAuthorityConvergence, true);
  assert.equal(policy.precedence,'none');
  assert.deepEqual(policy.authorities.map(x=>x.id),['typespec','json-schema']);
  assert.notEqual(policy.authorities[0].path,policy.authorities[1].path);
  assert.ok(policy.authorities.every(x=>x.origin==='independently_human_authored'));
  assert.equal(policy.generatedJsonSchemaUse,'diagnostic_comparison_only');
  assert.equal(policy.parityGate.currentStatus,'not_executed');
  assert.equal(policy.parityGate.fullCompilerAndDifferentialValidationRequired,true);
  assert.equal(policy.database.ormMayGenerateReviewProposalOnly,true);
};
inspect(original);
assert.match(typeSpec, /namespace Ores\.Orm;/);
assert.match(typeSpec, /model DocumentRow\s*\{/);
for (const name of ['workspace_id','id','title','note']) {
  assert.match(typeSpec,new RegExp('\\b'+name+':\\s*string'));
}
assert.match(typeSpec, /note:\s*string\s*\|\s*null/);
assert.match(guest, /define module orm_schema as/);
assert.match(guest, /pub fnc diff_checked\(/);
assert.match(guest, /return Ok\(new OrmSchemaProposal\("stop_for_evaluation"/);
assert.match(guest, /column_shapes_equal_only/);
assert.match(guest, /block_drop_or_rename_column/);
assert.match(tests, /"Oreslang neutral column-schema diff contracts passed"/);
console.log('SCHEMA_HOST_CASE=authored-sample-admission PASS');
let count=1;
function mustReject(name, mutate) {
  const data=structuredClone(original);mutate(data);
  assert.throws(()=>inspect(data),undefined,name+' should reject');
  count++;
  console.log('SCHEMA_HOST_CASE='+name+' PASS');
}
mustReject('missing-required-key', d=>d.json.$defs.DocumentRow.required.pop());
mustReject('nullable-drift', d=>d.overlay.columns[3].nullable=false);
mustReject('storage-column-drift', d=>d.overlay.columns[0].name='owner');
mustReject('type-family-drift', d=>d.overlay.columns[2].typeFamily='json');
mustReject('missing-tenant-primary-key', d=>d.overlay.primaryKey.shift());
mustReject('unsafe-auto-apply', d=>d.overlay.migrationPolicy.allowDirectOrmApply=true);
mustReject('unsafe-auto-rename', d=>d.overlay.migrationPolicy.allowAutoDropOrRename=true);
mustReject('unreviewed-rls', d=>d.overlay.manualReviewRequired.splice(d.overlay.manualReviewRequired.indexOf('rls_policies'),1));
mustReject('authority-precedence', d=>d.policy.precedence='typespec');
mustReject('false-parity-status', d=>d.policy.parityGate.currentStatus='passed');
mustReject('derived-schema-over-peer', d=>d.policy.generatedJsonSchemaUse='replace_authored');
console.log('SCHEMA_HOST_SCENARIOS='+count+'/'+count+' PASS (NOT TYPESPEC, ORESLANG, OR DPM EXECUTION)');
