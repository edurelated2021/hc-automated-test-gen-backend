
import requests

class JiraService:
    def fetch_story(self, base_url: str, story_key: str, token: str) -> str:
        if not token:
            raise Exception('Jira token not configured in Admin Settings')
        url = base_url.rstrip('/') + '/rest/api/3/issue/' + story_key
        headers = {
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise Exception('Jira API error ' + str(resp.status_code) + ' ' + resp.text)
        data = resp.json()
        fields = data.get('fields', {})
        summary = fields.get('summary', '')
        description_obj = fields.get('description')
        description_text = ''
        # Jira Cloud may return description as Atlassian Document Format
        if isinstance(description_obj, dict) and description_obj.get('content'):
            for block in description_obj.get('content', []):
                for inner in block.get('content', []):
                    if inner.get('text'):
                        description_text += inner.get('text') + ''
        elif isinstance(description_obj, str):
            description_text = description_obj
        acceptance = ''
        # Try acceptance criteria in common custom fields
        for key in ['customfield_10034', 'Acceptance Criteria', 'acceptanceCriteria']:
            val = fields.get(key)
            if isinstance(val, str):
                acceptance = val
                break
            if isinstance(val, dict):
                # If in ADF format
                for block in val.get('content', []):
                    for inner in block.get('content', []):
                        if inner.get('text'):
                            acceptance += inner.get('text') + ''
                break
        story_text = 'Summary:' + summary + 'Description:' + description_text + 'Acceptance Criteria:' + acceptance
        return story_text
