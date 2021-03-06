import sqlparse
from sqlparse.sql import IdentifierList, TokenList, Where, Identifier
import sqlparse.tokens as Tokens


class SqlParser:
    before_from_keywords = ['SELECT']
    from_keywords = ['FROM',
                     'INNER JOIN', 'CROSS JOIN', 'LEFT OUTER JOIN',
                     'RIGHT OUTER JOIN', 'FULL OUTER JOIN', "ON", "AND", "OR"]
    after_from_keywords = ['WHERE', 'GROUP', "BY",
                           'HAVING', 'ORDER', 'UNION', 'LIMIT', "OFFSET"]
    all_supported_keywords = \
        before_from_keywords + from_keywords + after_from_keywords

    def __init__(self, sql):
        self.tokens = sqlparse.parse(sql)[0].tokens
        self.keywords = find_keywords(self.tokens,
                                      self.all_supported_keywords,
                                      True)

    @property
    def fields(self):
        for token in self.tokens[
                     self.keywords['SELECT'] + 1:self.keywords['FROM']]:
            if isinstance(token, Identifier):
                return list(self.parse_columns([token]))
            if isinstance(token, IdentifierList):
                return list(self.parse_columns(token.get_identifiers()))

    @staticmethod
    def parse_columns(tokens):
        for token in tokens:
            offsets = find_keywords(token.tokens, ["AS"])
            if "AS" in offsets:
                yield (
                    extract(token.tokens[:offsets["AS"]]).value,
                    extract(token.tokens[offsets["AS"] + 1:]).value
                )
            else:
                yield (token.value, token.value)

    def fields_with_types(self, conn):
        # TODO: replace xxx with sth autogenerated
        cur = conn.cursor()
        cur.execute(
            "CREATE TEMPORARY TABLE xxx AS " +
            self.sql_without_limit +
            " LIMIT 0")
        cur.execute("SELECT column_name, data_type"
                    "  FROM INFORMATION_SCHEMA.COLUMNS"
                    " WHERE table_name = 'xxx'"
                    " ORDER BY ordinal_position")

        if self.fields is None:
            for field_name, field_type in cur.fetchall():
                yield (field_name, field_type, '"%s"' % field_name, ())
        else:
            for (field_name, field_type), (field_expr, field_alias) \
                    in zip(cur.fetchall(), self.fields):
                print(field_name, field_type, field_expr)
                yield (field_name, field_type, field_expr, ())
        cur.execute("DROP TABLE xxx")
        conn.commit()

    @property
    def from_(self):
        end_from = min(self.keywords.get(kw, len(self.tokens))
                       for kw in self.after_from_keywords)

        return extract(self.tokens[self.keywords['FROM'] + 1:end_from]).value

    @property
    def where(self):
        if 'WHERE' in self.keywords:
            token = self.tokens[self.keywords['WHERE']]
            return extract(token.tokens[1:]).value

    @property
    def sql_without_limit(self):
        if "LIMIT" in self.keywords:
            return extract(self.tokens[:self.keywords["LIMIT"]]).value
        else:
            return extract(self.tokens).value


def find_keywords(tokens, supported_keywords, raise_if_unknown=False):
    keyword_offset = {}
    for idx, token in enumerate(tokens):
        if raise_if_unknown and \
                        token.ttype == Tokens.Keyword and \
                        token.value.upper() not in supported_keywords:
            raise ValueError("Unsupported keyword %s" % token.value.upper())

        if isinstance(token, Where) and "WHERE" in supported_keywords:
            keyword_offset["WHERE"] = idx
        if token.match(Tokens.Keyword, supported_keywords) or \
                token.match(Tokens.DML, supported_keywords):
            keyword_offset[token.value.upper()] = idx
    return keyword_offset


def extract(token_list):
    tokens = list(TokenList(token_list).flatten())
    for token in tokens:
        if token.is_whitespace():
            token.value = " "
    return TokenList(tokens)
