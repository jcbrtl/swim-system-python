from abc import ABC, abstractmethod

from swimai.reacon.utils import ReconUtils
from swimai.structure.structs import ValueBuilder, Text, Bool, Attr, Value, Record


class Parser(ABC):
    pass


class BlockParser(Parser):

    @staticmethod
    async def parse(message, parser, output=None, builder=None):
        message = message.strip()

        if builder is None:
            builder = parser.create_value_builder()

        if output is None:
            output = await parser.parse_block_expression(message)

    @staticmethod
    async def parse_block(message, parser):
        return await BlockParser.parse(message, parser)


class ReconParser:

    async def parse_attr(self, message):
        return await AttrParser.parse_attr(message, self)

    async def parse_ident(self, message):
        return await IdentParser.parse_ident(message, self)

    async def parse_block_string(self, recon_string):
        message = InputMessage(recon_string)
        return await self.parse_block(message)

    async def parse_block(self, message):
        return await BlockParser.parse_block(message, self)

    async def parse_block_expression(self, message):
        return await self.parse_lambda_func(message)

    async def parse_lambda_func(self, message):
        return await LambdaFuncParser.parse_lambda_func(message, self)

    async def parse_conditional_operator(self, message, builder):
        return await ConditionalOperatorParser.parse_conditional_operator(message, self, builder)

    async def parse_or_operator(self, message, builder):
        return await OrOperatorParser.parse_or_operator(message, self, builder)

    async def parse_and_operator(self, message, builder):
        return await AndOperatorParser.parse_and_operator(message, self, builder)

    async def parse_bitwise_or_operator(self, message, builder):
        return await BitwiseOrOperatorParser.parse_bitwise_or_operator(message, self, builder)

    async def parse_bitwise_xor_operator(self, message, builder):
        return await BitwiseXorOperatorParser.parse_bitwise_xor_operator(message, self, builder)

    async def parse_bitwise_and_operator(self, message, builder):
        return await BitwiseAndOperator.parse_bitwise_and_operator(message, self, builder)

    async def parse_comparison_operator(self, message, builder):
        return await ComparisonOperatorParser.parse_comparison_operator(message, self, builder)

    async def parse_attr_expression(self, message, builder):
        return await AttrExpressionParser.parse_attr_expression(message, self, builder)

    async def parse_additive_operator(self, message, builder):
        return await AdditiveOperatorParser.parse_additive_operator(message, self, builder)

    async def parse_multiplicative_operator(self, message, builder):
        return await MultiplicativeOperatorParser.parse_multiplicative_operator(message, self, builder)

    async def parse_prefix_operator(self, message, builder):
        return await PrefixOperatorParser.parse_prefix_operator(message, self, builder)

    async def parse_invoke_operator(self, message, builder):
        return await InvokeOperatorParser.parse_invoke_operator(message, self, builder)

    async def parse_primary(self, message, builder):
        return await PrimaryParser.parse_primary(message, self, builder)

    async def parse_literal(self, message, builder):
        return await LiteralParser.parse_literal(message, self, builder)


class ReconStructureParser(ReconParser):

    async def create_ident(self, value):
        if isinstance(value, Text):
            if value == 'true':
                return Bool.get_from(True)
            elif value == 'false':
                return Bool.get_from(False)

        return Text.get_from(value)

    async def create_attr(self, key, value=Value.extant()):
        return Attr.of(key, value)

    async def create_record_builder(self):
        return Record.create()

    async def create_value_builder(self):
        return ValueBuilder()


class LambdaFuncParser(Parser):

    @staticmethod
    async def parse_lambda_func(message, parser):
        return await LambdaFuncParser.parse(message, parser)

    @staticmethod
    async def parse(message, parser, output=None, builder=None):
        if output is None:
            output = await parser.parse_conditional_operator(message, builder=builder)


class ConditionalOperatorParser(Parser):

    @staticmethod
    async def parse_conditional_operator(message, parser, builder):
        return await ConditionalOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, if_output=None, then_output=None, else_output=None, builder=None):
        if if_output is None:
            if_output = await parser.parse_or_operator(message, builder)


class OrOperatorParser(Parser):

    @staticmethod
    async def parse_or_operator(message, parser, builder):
        return await OrOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, lhs_output=None, rhs_output=None, builder=None):
        if lhs_output is None:
            lhs_output = await parser.parse_and_operator(message, builder)


class AndOperatorParser(Parser):

    @staticmethod
    async def parse_and_operator(message, parser, builder):
        return await AndOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, lhs_output=None, rhs_output=None, builder=None):
        if lhs_output is None:
            lhs_output = await parser.parse_bitwise_or_operator(message, builder)


class BitwiseOrOperatorParser(Parser):

    @staticmethod
    async def parse_bitwise_or_operator(message, parser, builder):
        return await BitwiseOrOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, lhs_output=None, rhs_output=None, builder=None):
        if lhs_output is None:
            lhs_output = await parser.parse_bitwise_xor_operator(message, builder)


class BitwiseXorOperatorParser(Parser):

    @staticmethod
    async def parse_bitwise_xor_operator(message, parser, builder):
        return await BitwiseXorOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, lhs_output=None, rhs_output=None, builder=None):
        if lhs_output is None:
            lhs_output = await parser.parse_bitwise_and_operator(message, builder)


class BitwiseAndOperator(Parser):

    @staticmethod
    async def parse_bitwise_and_operator(message, parser, builder):
        return await BitwiseAndOperator.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, lhs_output=None, rhs_output=None, builder=None):
        if lhs_output is None:
            lhs_output = await parser.parse_comparison_operator(message, builder)


class ComparisonOperatorParser(Parser):

    @staticmethod
    async def parse_comparison_operator(message, parser, builder):
        return await ComparisonOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, lhs_output=None, operator_output=None, rhs_output=None, builder=None):
        if lhs_output is None:
            lhs_output = await parser.parse_attr_expression(message, builder)


class AttrExpressionParser(Parser):

    @staticmethod
    async def parse_attr_expression(message, parser, builder):
        return await AttrExpressionParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, field_output=None, value_output=None, builder=None):

        char = message.head()

        if char == '@':
            if field_output is None:
                field_output = await parser.parse_attr(message)

            record_builder = await parser.create_record_builder()
            record_builder.add(field_output)
            return record_builder

        elif ReconUtils.is_ident_start_char(ord(char)):
            if value_output is None:
                value_output = await parser.parse_additive_operator(message, builder)

            if builder is None:
                builder = await parser.create_value_builder()

            builder.add(value_output)
            return builder.bind()


class AttrParser(Parser):

    @staticmethod
    async def parse_attr(message, parser):
        return await AttrParser.parse(message, parser)

    @staticmethod
    async def parse(message, parser, key_output=None, value_output=None):

        if message.head() == '@':
            message.step()
            if key_output is None:
                key_output = await parser.parse_ident(message)

            if message.head() == '(':
                message.step()

                if message.head() == ')':
                    return await parser.create_attr(key_output)

                if value_output is None:
                    value_output = await parser.parse_block(message)

        return await parser.create_attr(key_output, value_output)


class IdentParser(Parser):

    @staticmethod
    async def parse_ident(message, parser):
        return await IdentParser.parse(message, parser)

    @staticmethod
    async def parse(message, parser, output=None):

        char = message.head()

        if await ReconUtils.is_ident_start_char(ord(char)):
            if output is None:
                output = ''

            output = output + char
            char = message.step()

            while await ReconUtils.is_ident_char(ord(char)):
                output = output + char
                char = message.step()

        return await parser.create_ident(output)


class AdditiveOperatorParser(Parser):

    @staticmethod
    async def parse_additive_operator(message, parser, builder):
        return await AdditiveOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, lhs_output=None, operator_output=None, rhs_output=None, builder=None):
        if lhs_output is None:
            lhs_output = await parser.parse_multiplicative_operator(message, builder)

            char = message.head()

            if char == '+':
                pass
            elif char == '-':
                pass
            else:
                return lhs_output


class MultiplicativeOperatorParser(Parser):

    @staticmethod
    async def parse_multiplicative_operator(message, parser, builder):
        return await MultiplicativeOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, lhs_output=None, operator_output=None, rhs_output=None, builder=None):
        if lhs_output is None:
            lhs_output = await parser.parse_prefix_operator(message, builder)

            char = message.head()

            if char == '*':
                pass
            elif char == '/':
                pass
            elif char == '%':
                pass
            else:
                return lhs_output


class PrefixOperatorParser(Parser):

    @staticmethod
    async def parse_prefix_operator(message, parser, builder):
        return await PrefixOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, operator_output=None, rhs_output=None, builder=None):

        char = message.head()

        if char == '!':
            pass
        elif char == '~':
            pass
        elif char == '-':
            pass
        elif char == '+':
            pass
        else:
            return await parser.parse_invoke_operator(message, builder)


class InvokeOperatorParser(Parser):

    @staticmethod
    async def parse_invoke_operator(message, parser, builder):
        return await InvokeOperatorParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, expr_output=None, args_output=None, builder=None):
        if expr_output is None:
            expr_output = await parser.parse_primary(message, builder)

            char = message.head()

            if char == '(':
                pass
            else:
                return expr_output


class PrimaryParser(Parser):

    @staticmethod
    async def parse_primary(message, parser, builder):
        return await PrimaryParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, expr_output=None, builder=None):

        char = message.head()

        if char == '(':
            pass
        else:
            if expr_output is None:
                expr_output = await parser.parse_literal(message, builder)

            return expr_output


class LiteralParser(Parser):

    @staticmethod
    async def parse_literal(message, parser, builder):
        return await LiteralParser.parse(message, parser, builder=builder)

    @staticmethod
    async def parse(message, parser, value_output=None, builder=None):
        char = message.head()

        if char == '(':
            pass
        elif char == '{':
            pass
        elif char == '[':
            pass
        elif await ReconUtils.is_ident_start_char(ord(char)):

            if value_output is None:
                value_output = await parser.parse_ident(message)

            if builder is None:
                builder = await parser.create_value_builder()

            builder.add(value_output)

            return builder.bind()


class InputMessage:

    def __init__(self, message):
        self.message = message
        self.index = 0

    def head(self):
        return self.message[self.index]

    def step(self):
        self.index = self.index + 1
        return self.head()

    def strip(self):
        self.message = self.message.strip()
        return self