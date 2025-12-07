"""
중복된 Function name 확인 스크립트
"""
import os
from sqlalchemy import create_engine, text

# DB 연결 (직접 지정 - docker-compose 기준)
database_url = os.getenv("DATABASE_URL", "postgresql://runna_user:runna_password@localhost:5432/runna_db")
engine = create_engine(database_url)

print("=" * 80)
print("같은 Workspace 내에서 중복된 Function name 확인")
print("=" * 80)

# 중복된 name 조회
query = text("""
    SELECT
        w.name as workspace_name,
        w.alias as workspace_alias,
        f.name as function_name,
        COUNT(*) as duplicate_count,
        array_agg(f.id::text) as function_ids,
        array_agg(f.endpoint) as endpoints
    FROM functions f
    JOIN workspaces w ON f.workspace_id = w.id
    GROUP BY w.name, w.alias, f.name, f.workspace_id
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC;
""")

try:
    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

        if not rows:
            print("\n[OK] 중복된 Function name이 없습니다!")
            print("     안전하게 unique constraint를 추가할 수 있습니다.\n")
        else:
            print(f"\n[WARNING] 총 {len(rows)}개의 중복 그룹이 발견되었습니다:\n")

            for idx, row in enumerate(rows, 1):
                print(f"\n[{idx}] Workspace: {row.workspace_name} ({row.workspace_alias})")
                print(f"    Function Name: {row.function_name}")
                print(f"    중복 개수: {row.duplicate_count}개")
                print(f"    Function IDs: {row.function_ids}")
                print(f"    Endpoints: {row.endpoints}")
                print("-" * 80)

            print("\n[WARNING] Unique constraint를 추가하기 전에 중복을 제거해야 합니다.")
            print("          중복된 function들의 endpoint는 다르므로, name을 변경하거나 삭제해야 합니다.\n")

        # 전체 통계
        total_query = text("""
            SELECT
                COUNT(DISTINCT workspace_id) as workspace_count,
                COUNT(*) as total_function_count
            FROM functions;
        """)

        stats = conn.execute(total_query).fetchone()
        print("=" * 80)
        print(f"전체 통계:")
        print(f"  - Workspace 개수: {stats.workspace_count}")
        print(f"  - Function 총 개수: {stats.total_function_count}")
        print("=" * 80)

except Exception as e:
    print(f"\n[ERROR] 오류 발생: {e}")
    print("\nDB가 실행 중인지 확인해주세요:")
    print("  docker-compose up -d postgres")
