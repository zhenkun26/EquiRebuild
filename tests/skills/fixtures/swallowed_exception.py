def risky():
    try:
        return int("not-a-number")
    except ValueError:
        pass
    return 0
