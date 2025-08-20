from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

data = SqliteData(db_path='.gryt.db')
runtime = LocalRuntime()

runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello']}),
    CommandStep('world', {'cmd': ['echo', 'world']}),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
