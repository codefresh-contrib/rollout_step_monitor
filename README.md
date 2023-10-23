# Rollout Step Monitor

Step to monitor a Rollout Step in a Codefresh's GitOps Runtime

## Development

-   To activate venv

```sh
python3 -m venv venv --clear
source venv/bin/activate
```

-   Download all dependencies

```sh
pip install --upgrade pip
pip install -r requirements.txt
```

-   Update list of requirements:

```sh
pip freeze > requirements.txt
```

## Running it

Create a variables.env file with the following content:

```sh
ENDPOINT=https://g.codefresh.io/2.0/api/graphql
CF_API_KEY=XYZ
RUNTIME=<the_runtime_name>
NAMESPACE=<the_namespace>
APPLICATION=<the_app_name>
ROLLOUT=<the_rollout_name>
COMMIT_SHA=<the_commit_sha_of_the_release>
STEP_INDEX=<step_index_starting_from_zero>
```

-   Running in shell:

```sh
export $( cat variables.env | xargs ) && python monitor_rollout_step.py
```

-   Running as a container:

```sh
export image_name="`yq .name service.yaml`"
export image_tag="`yq .version service.yaml`"
export registry="franciscocodefresh" ## Docker Hub
docker build -t ${image_name} .
docker run --rm --env-file variables.env ${image_name}
```

-   Pushing the image:

```sh
docker tag ${image_name} ${registry}/${image_name}:${image_tag}
docker push ${registry}/${image_name}:${image_tag}
```
