// Independent human-authored TypeSpec authority. Never overwrite peer JSON Schema.
namespace Ores.Orm;
model DocumentRow {
  @format("uuid")
  workspace_id: string;
  @format("uuid")
  id: string;
  title: string;
  note: string | null;
}
