DESCRIPTION = """
할일을 검색하거나 목록을 조회합니다.
- 검색 조건(keyword, status, project)이 모두 없다면 자동으로 최근 5건의 할일을 조회합니다.
- '최근 할일 보여줘'와 같은 요청 시 키워드 없이 이 도구를 호출하세요.
- 결과값은 `todos`와 `markdown_table`을 포함한 객체입니다.
- `todos`는 할일 목록(List)이며, 각 항목은 id, title(제목), description(설명), status(상태), priority(우선순위), project(프로젝트), due_date(마감일) 등을 포함합니다.
- `markdown_table`은 사용자에게 바로 보여줄 수 있는 마크다운 표 문자열입니다.
"""
