#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="${JIUWENSWARM_ROOT:-/opt/JiuwenSwarm}"
COMPONENT_DIR="${ROOT_DIR}/components"
DOWNLOAD_DIR="${ROOT_DIR}/.downloads"
MANIFEST_FILE="${ROOT_DIR}/components.sha256"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${SCRIPT_DIR}/../components.env" ]]; then
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/../components.env"
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing required command: %s\n' "$1" >&2
    exit 1
  }
}

for command_name in curl tar unzip sha256sum sha512sum python3; do
  require_command "${command_name}"
done

mkdir -p "${COMPONENT_DIR}" "${DOWNLOAD_DIR}" "${ROOT_DIR}/runtime" "${ROOT_DIR}/bin"
touch "${MANIFEST_FILE}"

download() {
  local url="$1"
  local destination="$2"
  curl --fail --location --retry 3 --retry-delay 2 --connect-timeout 20 \
    --output "${destination}.part" "${url}"
  mv -f -- "${destination}.part" "${destination}"
}

verify_sha256() {
  local file="$1"
  local expected="$2"
  printf '%s  %s\n' "${expected}" "${file}" | sha256sum --check --status
}

verify_sha512() {
  local file="$1"
  local expected="$2"
  printf '%s  %s\n' "${expected}" "${file}" | sha512sum --check --status
}

record_sha256() {
  local file="$1"
  local relative_file="${file#${ROOT_DIR}/}"
  printf '%s  %s\n' "$(sha256sum "${file}" | awk '{print $1}')" "${relative_file}" >> "${MANIFEST_FILE}"
}

install_tar_component() {
  local name="$1"
  local version="$2"
  local url="$3"
  local checksum_type="$4"
  local checksum="$5"
  local archive="${DOWNLOAD_DIR}/${name}-${version}.tar.gz"
  local destination="${COMPONENT_DIR}/${name}/${version}"

  if [[ -x "${destination}/bin/${name}" || -x "${destination}/${name}" ]]; then
    printf '%s %s already present\n' "${name}" "${version}"
    return
  fi

  download "${url}" "${archive}"
  if [[ "${checksum_type}" == sha256 ]]; then
    verify_sha256 "${archive}" "${checksum}"
  else
    verify_sha512 "${archive}" "${checksum}"
  fi
  mkdir -p "${destination}"
  tar -xzf "${archive}" --strip-components=1 -C "${destination}"
  rm -f -- "${archive}"
}

printf 'Installing JiuwenSwarm components under %s\n' "${ROOT_DIR}"

install_tar_component prometheus "${PROMETHEUS_VERSION}" \
  "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz" \
  sha256 "${PROMETHEUS_SHA256}"

install_tar_component alertmanager "${ALERTMANAGER_VERSION}" \
  "https://github.com/prometheus/alertmanager/releases/download/v${ALERTMANAGER_VERSION}/alertmanager-${ALERTMANAGER_VERSION}.linux-amd64.tar.gz" \
  sha256 "${ALERTMANAGER_SHA256}"

install_tar_component grafana "${GRAFANA_VERSION}" \
  "https://dl.grafana.com/grafana/release/${GRAFANA_VERSION}/grafana_${GRAFANA_VERSION}_${GRAFANA_BUILD}_linux_amd64.tar.gz" \
  sha256 "${GRAFANA_SHA256}"

loki_destination="${COMPONENT_DIR}/loki/${LOKI_VERSION}"
if [[ ! -x "${loki_destination}/loki-linux-amd64" ]]; then
  loki_archive="${DOWNLOAD_DIR}/loki-${LOKI_VERSION}.zip"
  download "https://github.com/grafana/loki/releases/download/v${LOKI_VERSION}/loki-linux-amd64.zip" "${loki_archive}"
  verify_sha256 "${loki_archive}" "${LOKI_SHA256}"
  mkdir -p "${loki_destination}"
  unzip -q -o "${loki_archive}" -d "${loki_destination}"
  chmod 0755 "${loki_destination}/loki-linux-amd64"
  rm -f -- "${loki_archive}"
else
  printf 'loki %s already present\n' "${LOKI_VERSION}"
fi

loki_config="${loki_destination}/loki-config.yaml"
if [[ ! -e "${loki_config}" ]]; then
  cat > "${loki_config}" <<EOF
auth_enabled: false

server:
  http_listen_address: ${LOKI_HTTP_HOST}
  http_listen_port: ${LOKI_HTTP_PORT}
  grpc_listen_port: ${LOKI_GRPC_PORT}

common:
  path_prefix: ${loki_destination}/data
  storage:
    filesystem:
      chunks_directory: ${loki_destination}/data/chunks
      rules_directory: ${loki_destination}/data/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

ruler:
  alertmanager_url: ""
  enable_api: true

limits_config:
  allow_structured_metadata: false
  volume_enabled: true
  retention_period: 168h

analytics:
  reporting_enabled: false
EOF
  chmod 0644 "${loki_config}"
else
  printf 'loki config already present: %s\n' "${loki_config}"
fi

alloy_destination="${COMPONENT_DIR}/alloy/${ALLOY_VERSION}"
if [[ ! -x "${alloy_destination}/alloy" ]]; then
  alloy_archive="${DOWNLOAD_DIR}/alloy-${ALLOY_VERSION}-linux-amd64.zip"
  if [[ ! -f "${alloy_archive}" ]]; then
    download "https://github.com/grafana/alloy/releases/download/v${ALLOY_VERSION}/alloy-boringcrypto-linux-amd64.zip" "${alloy_archive}"
  fi
  verify_sha256 "${alloy_archive}" "${ALLOY_SHA256}"
  mkdir -p "${alloy_destination}"
  unzip -q -o "${alloy_archive}" -d "${alloy_destination}"
  # The release archive names the standalone binary after its build variant.
  # Normalize it inside the project-owned component directory so callers have
  # one stable path without changing the upstream artifact.
  if [[ -f "${alloy_destination}/alloy-boringcrypto-linux-amd64" ]]; then
    mv -f -- "${alloy_destination}/alloy-boringcrypto-linux-amd64" "${alloy_destination}/alloy"
  fi
  chmod 0755 "${alloy_destination}/alloy"
  rm -f -- "${alloy_archive}"
else
  printf 'alloy %s already present\n' "${ALLOY_VERSION}"
fi

opensearch_destination="${COMPONENT_DIR}/opensearch/${OPENSEARCH_VERSION}"
if [[ ! -x "${opensearch_destination}/bin/opensearch" ]]; then
  opensearch_archive="${DOWNLOAD_DIR}/opensearch-${OPENSEARCH_VERSION}-linux-x64.tar.gz"
  download "https://artifacts.opensearch.org/releases/bundle/opensearch/${OPENSEARCH_VERSION}/opensearch-${OPENSEARCH_VERSION}-linux-x64.tar.gz" "${opensearch_archive}"
  verify_sha512 "${opensearch_archive}" "${OPENSEARCH_SHA512}"
  mkdir -p "${opensearch_destination}"
  tar -xzf "${opensearch_archive}" --strip-components=1 -C "${opensearch_destination}"
  rm -f -- "${opensearch_archive}"
else
  printf 'opensearch %s already present\n' "${OPENSEARCH_VERSION}"
fi

rundeck_destination="${COMPONENT_DIR}/rundeck/${RUNDECK_VERSION}"
if [[ ! -f "${rundeck_destination}/${RUNDECK_RPM}" ]]; then
  mkdir -p "${rundeck_destination}"
  rundeck_url="https://packages.rundeck.com/pagerduty/rundeck/rpm_any/rpm_any/x86_64/${RUNDECK_RPM}"
  download "${rundeck_url}" "${rundeck_destination}/${RUNDECK_RPM}"
else
  printf 'rundeck %s already present\n' "${RUNDECK_VERSION}"
fi

ansible_destination="${COMPONENT_DIR}/ansible/${ANSIBLE_VERSION}"
if [[ ! -x "${ansible_destination}/venv/bin/ansible" ]]; then
  mkdir -p "${ansible_destination}"
  python3 -m venv "${ansible_destination}/venv"
  "${ansible_destination}/venv/bin/python" -m pip install --no-cache-dir --upgrade "${ANSIBLE_PACKAGE}==${ANSIBLE_VERSION}"
else
  printf 'ansible %s already present\n' "${ANSIBLE_VERSION}"
fi

kubectl_version="${KUBECTL_VERSION}"
if [[ "${kubectl_version}" == stable ]]; then
  kubectl_version="$(curl --fail --location --silent --show-error https://dl.k8s.io/release/stable.txt)"
fi
kubectl_destination="${ROOT_DIR}/bin/kubectl"
if [[ ! -x "${kubectl_destination}" ]]; then
  kubectl_sha="${DOWNLOAD_DIR}/kubectl-${kubectl_version}.sha256"
  download "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl" "${kubectl_destination}"
  download "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl.sha256" "${kubectl_sha}"
  printf '%s  %s\n' "$(tr -d '[:space:]' < "${kubectl_sha}")" "${kubectl_destination}" | sha256sum --check --status
  chmod 0755 "${kubectl_destination}"
  rm -f -- "${kubectl_sha}"
else
  printf 'kubectl %s already present\n' "${kubectl_version}"
fi

cat > "${ROOT_DIR}/resolved-versions.env" <<EOF
PROMETHEUS_VERSION=${PROMETHEUS_VERSION}
ALERTMANAGER_VERSION=${ALERTMANAGER_VERSION}
GRAFANA_VERSION=${GRAFANA_VERSION}
LOKI_VERSION=${LOKI_VERSION}
LOKI_HTTP_HOST=${LOKI_HTTP_HOST}
LOKI_HTTP_PORT=${LOKI_HTTP_PORT}
LOKI_GRPC_PORT=${LOKI_GRPC_PORT}
ALLOY_VERSION=${ALLOY_VERSION}
OPENSEARCH_VERSION=${OPENSEARCH_VERSION}
RUNDECK_VERSION=${RUNDECK_VERSION}
ANSIBLE_VERSION=${ANSIBLE_VERSION}
ANSIBLE_PACKAGE=${ANSIBLE_PACKAGE}
KUBECTL_VERSION=${kubectl_version}
EOF

: > "${MANIFEST_FILE}"
record_sha256 "${COMPONENT_DIR}/prometheus/${PROMETHEUS_VERSION}/prometheus"
record_sha256 "${COMPONENT_DIR}/alertmanager/${ALERTMANAGER_VERSION}/alertmanager"
record_sha256 "${COMPONENT_DIR}/grafana/${GRAFANA_VERSION}/bin/grafana"
record_sha256 "${COMPONENT_DIR}/loki/${LOKI_VERSION}/loki-linux-amd64"
record_sha256 "${COMPONENT_DIR}/alloy/${ALLOY_VERSION}/alloy"
record_sha256 "${COMPONENT_DIR}/opensearch/${OPENSEARCH_VERSION}/bin/opensearch"
record_sha256 "${COMPONENT_DIR}/rundeck/${RUNDECK_VERSION}/${RUNDECK_RPM}"
record_sha256 "${COMPONENT_DIR}/ansible/${ANSIBLE_VERSION}/venv/bin/ansible"
record_sha256 "${ROOT_DIR}/bin/kubectl"

rm -rf -- "${DOWNLOAD_DIR}"
printf 'Component installation complete. Resolved versions: %s\n' "${ROOT_DIR}/resolved-versions.env"
