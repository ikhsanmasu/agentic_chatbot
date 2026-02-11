from sqlalchemy import Engine, text


def get_schema_info(engine: Engine) -> str:
    """Query ClickHouse system.columns and return a formatted string for LLM context."""
    query = text("""
        SELECT
            database,
            table,
            name,
            type,
            default_kind,
            default_expression,
            comment
        FROM system.columns
        WHERE database NOT IN ('system', 'INFORMATION_SCHEMA', 'information_schema')
        ORDER BY database, table, position
    """)

    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    if not rows:
        return "No tables found in the database."

    tables: dict[str, list[str]] = {}
    for database, table, col_name, col_type, default_kind, default_expr, comment in rows:
        full_name = f"{database}.{table}"
        if full_name not in tables:
            tables[full_name] = []
        default_str = f" DEFAULT {default_expr}" if default_kind else ""
        comment_str = f"  -- {comment}" if comment else ""
        tables[full_name].append(f"  {col_name} {col_type}{default_str}{comment_str}")

    parts = []
    for table_name, columns in tables.items():
        cols = "\n".join(columns)
        parts.append(f"TABLE {table_name}:\n{cols}")

    return "\n\n".join(parts)
