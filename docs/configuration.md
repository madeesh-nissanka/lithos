# Configuration

LITHOS uses a YAML or JSON configuration file to control adapter behavior,
rate limits, and other settings. Pass the config file with `--config`.

## Configuration File Structure

```yaml
# Global polite email for OpenAlex/Crossref
polite_email: "<your-email>"

# Per-adapter configuration
openalex:
  enabled: true
  rate_limit: 10.0    # requests per second
  burst: 10           # burst allowance
  polite_email: "<your-email>"

crossref:
  enabled: true
  rate_limit: 50.0
  burst: 50

semantic_scholar:
  enabled: true
  rate_limit: 1.0
  burst: 5
  api_key: "your_api_key"  # Optional, for higher rate limits

arxiv:
  enabled: true
  rate_limit: 3.0
  burst: 5

europe_pmc:
  enabled: true
  rate_limit: 10.0
  burst: 10

core:
  enabled: false        # Requires API key
  api_key: "your_api_key"
  rate_limit: 10.0
  burst: 10

doaj:
  enabled: true
  rate_limit: 5.0
  burst: 10

unpaywall:
  enabled: true
  rate_limit: 10.0
  burst: 20
```

## Adapter Options

Each adapter supports these options:
- `enabled` (bool) - Enable/disable the adapter
- `rate_limit` (float) - Maximum requests per second
- `burst` (int) - Burst allowance above rate limit
- `max_retries` (int) - Max retry attempts (default: 3)
- `timeout` (int) - Request timeout in seconds (default: 30)
- `polite_email` (str) - Email for polite pool identification
- `api_key` (str) - API key for authenticated access
- `extra_params` (dict) - Adapter-specific extra parameters

## Environment Variables

- `SCHOLAR_MAILTO` - Default polite email if not set in config

## Example: Minimal Config

```yaml
polite_email: "<your-email>"
semantic_scholar:
  api_key: "abc123"
core:
  enabled: true
  api_key: "def456"
```

## Example: Disable Specific Sources

```yaml
polite_email: "<your-email>"
core:
  enabled: false
semantic_scholar:
  enabled: false
```

## Loading Config in Python

```python
import lithos
from pathlib import Path

config = lithos.load_config(Path("lithos.yaml"))
lithos.init_adapters(config)
```