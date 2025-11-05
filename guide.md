## I want to...

### Generations

**Create a new generation**

```shell
gryt generation new <generation(example v2.2.0)>
```

**Update my local db with the new or edited generation**

```shell
gryt generation update <generation>
```

**Generate test scaffolding for changes in a generation**

```shell
# for a specific change
gryt generation gen-test --change <change ID>

# for all changes listed in a generation
gryt generation gen-test --all

# for regenerate
gryt generation gen-test [--all or --change] --force
```

**Promte a generation to a full release**

```bash
gryt generation promote <generate ID> [--no-tag (don't recreate git tag, optional)]
```

### Evolutions

**Start a new evolution**

```shell
gryt evolution start <generation> --change <change ID>
```

**Link a test to evolution**

```shell
gryt evolution link-pipeline --pipeline <pipelinename.py> --change <change ID> --generation <generation ID>
```

**Prove a evolutionary change is complete**

```shell
gryt evolution prove <change tag>
```

**Check the of evolutions within a generation**

```shell
gryt evolution list <change ID>
```


### Keeping the remote up-to-date

**Check the status of my state, vs remote state**

```shell
gryt sync status  
```

**Pull in the latest change**

```shell
gryt sync pull
```

***Push my change to the remote db**

```shell
gryt sync push 
```

