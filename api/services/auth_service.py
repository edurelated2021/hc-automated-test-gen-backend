
# Very basic auth service for demo purposes only.
class AuthService:
    def authenticate(self, username: str, password: str) -> bool:
        return username == 'admin' and password == 'default'
