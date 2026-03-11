DESCRIPTION = """
메모를 검색하거나 목록을 조회합니다.
- 검색 조건(keyword)이 없으면 자동으로 최근 5건의 메모를 조회합니다.
- '최근 메모 보여줘'와 같은 요청 시 키워드 없이 이 도구를 호출하세요.
- 결과값은 `memos`와 `markdown_table`을 포함한 객체입니다.
- `memos`는 메모 목록이며, 각 항목은 id, title(제목), content(본문), created_at 등을 포함합니다.
- `markdown_table`은 사용자에게 바로 보여줄 수 있는 마크다운 표 문자열입니다.
"""
