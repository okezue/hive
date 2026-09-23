class Err(Exception):
    code='error'

    def __init__(s, msg, hint=None):
        super().__init__(msg)
        s.msg, s.hint = msg, hint

    def __str__(s):
        return f'{s.msg} ({s.hint})' if s.hint else s.msg


class Missing(Err): code='missing'
class Bad(Err): code='bad'
class Denied(Err): code='denied'
class Clash(Err): code='clash'
class Anon(Err): code='anon'
