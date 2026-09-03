import cppcheck


@cppcheck.checker
def cast(cfg, data):
    for token in cfg.tokenlist:
        if token.str != "(" or not token.astOperand1 or token.astOperand2:
            continue
        if token.astOperand1.str == "{":
            continue
        typetok = token.next
        if not typetok.isName:
            continue
        if token.astOperand1.isNumber:
            continue
        if typetok.str == "void":
            continue
        cppcheck.reportError(token, "information", "found a cast")
