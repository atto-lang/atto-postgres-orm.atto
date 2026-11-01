// Peer TypeSpec authority for the portable schema catalog envelope.
// Authored independently from contracts/orm-catalog.schema.json.
// This is a schema declaration, not a DB driver or an SQL emitter.
namespace Ores.Orm;

enum ColumnKind {
  uuid: "uuid",
  string: "string",
  int32: "int32",
  int64: "int64",
  boolean: "boolean",
  json: "json",
  timestamp: "timestamp",
  bytes: "bytes",
}

model Column {
  @minLength(1)
  @maxLength(63)
  @pattern("^[A-Za-z_][A-Za-z0-9_]*$")
  stable_id: string;

  @minLength(1)
  @maxLength(63)
  @pattern("^[A-Za-z_][A-Za-z0-9_]*$")
  name: string;

  kind: ColumnKind;
  nullable: boolean;
}

model Table {
  @minLength(1)
  @maxLength(63)
  @pattern("^[A-Za-z_][A-Za-z0-9_]*$")
  stable_id: string;

  @minLength(1)
  @maxLength(63)
  @pattern("^[A-Za-z_][A-Za-z0-9_]*$")
  name: string;

  @minItems(1)
  @maxItems(64)
  columns: Column[];
}

model Catalog {
  schema_version: "ores.orm.catalog/v1";
  @maxItems(256)
  tables: Table[];
}
