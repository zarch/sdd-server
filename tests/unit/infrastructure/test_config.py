"""Tests for configuration management."""

from pathlib import Path

import pytest

from sdd_server.infrastructure.config import (
    AuditSettings,
    Environment,
    ExecutionConfig,
    HealthCheckSettings,
    LoggingConfig,
    LogLevel,
    MetricsSettings,
    ObservabilityConfig,
    PluginConfig,
    RateLimitSettings,
    RetrySettings,
    SDDConfig,
    SecurityConfig,
    ServerConfig,
    get_config,
    reload_config,
)


class TestServerConfig:
    """Tests for ServerConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ServerConfig()
        assert config.host == "localhost"
        assert config.port == 8000
        assert config.debug is False
        assert config.workers == 1
        assert config.timeout_seconds == 300.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = ServerConfig(host="0.0.0.0", port=9000, debug=True, workers=4)
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.debug is True
        assert config.workers == 4


class TestExecutionConfig:
    """Tests for ExecutionConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ExecutionConfig()
        assert config.max_parallel_roles == 3
        assert config.role_timeout_seconds == 600.0
        assert config.enable_streaming is True
        assert config.failure_strategy == "continue_on_failure"

    def test_nested_retry_config(self) -> None:
        """Test nested retry configuration."""
        config = ExecutionConfig()
        assert config.retry.max_retries == 3
        assert config.retry.initial_delay == 1.0
        assert config.retry.jitter is True


class TestPluginConfig:
    """Tests for PluginConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = PluginConfig()
        assert "sdd_server.plugins" in config.discovery_paths
        assert config.enabled_plugins == []
        assert config.disabled_plugins == []
        assert config.auto_discover is True

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = PluginConfig(
            discovery_paths=["custom.plugins"],
            enabled_plugins=["architect"],
            disabled_plugins=["reviewer"],
            auto_discover=False,
        )
        assert config.discovery_paths == ["custom.plugins"]
        assert config.enabled_plugins == ["architect"]
        assert config.disabled_plugins == ["reviewer"]
        assert config.auto_discover is False


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = LoggingConfig()
        assert config.level == LogLevel.INFO
        assert config.output == "stderr"
        assert config.include_timestamp is True
        assert config.json_format is False

    def test_log_level_enum(self) -> None:
        """Test log level enum values."""
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"


class TestSecurityConfig:
    """Tests for SecurityConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SecurityConfig()
        assert config.rate_limit.requests_per_window == 100
        assert config.rate_limit.window_seconds == 60.0
        assert config.max_request_size == 10 * 1024 * 1024
        assert config.allowed_origins == ["*"]
        assert config.enable_input_validation is True

    def test_custom_rate_limit(self) -> None:
        """Test custom rate limit settings."""
        config = SecurityConfig(rate_limit=RateLimitSettings(requests_per_window=50))
        assert config.rate_limit.requests_per_window == 50


class TestObservabilityConfig:
    """Tests for ObservabilityConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ObservabilityConfig()
        assert config.metrics.prefix == "sdd"
        assert config.health.check_interval == 30.0
        assert config.audit.enabled is True
        assert config.enable_tracing is False


class TestSDDConfig:
    """Tests for main SDDConfig class."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SDDConfig()
        assert config.environment == Environment.DEVELOPMENT
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.execution, ExecutionConfig)
        assert isinstance(config.plugins, PluginConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.observability, ObservabilityConfig)

    def test_environment_enum(self) -> None:
        """Test environment enum values."""
        assert Environment.DEVELOPMENT == "development"
        assert Environment.STAGING == "staging"
        assert Environment.PRODUCTION == "production"
        assert Environment.TESTING == "testing"

    def test_to_dict(self) -> None:
        """Test converting configuration to dictionary."""
        config = SDDConfig()
        data = config.to_dict()

        assert data["environment"] == "development"
        assert "server" in data
        assert "execution" in data
        assert "plugins" in data
        assert "logging" in data
        assert "security" in data
        assert "observability" in data

        # Check nested values
        assert data["server"]["port"] == 8000
        assert data["execution"]["max_parallel_roles"] == 3
        assert data["logging"]["level"] == "INFO"

    def test_from_dict(self) -> None:
        """Test creating configuration from dictionary."""
        data = {
            "environment": "production",
            "server": {"port": 9000, "debug": False},
            "execution": {"max_parallel_roles": 5},
            "logging": {"level": "WARNING"},
        }
        config = SDDConfig._from_dict(data)

        assert config.environment == Environment.PRODUCTION
        assert config.server.port == 9000
        assert config.execution.max_parallel_roles == 5
        assert config.logging.level == LogLevel.WARNING

    def test_from_dict_invalid_environment(self) -> None:
        """Test handling invalid environment in dictionary."""
        data = {"environment": "invalid"}
        config = SDDConfig._from_dict(data)
        # Should fall back to default
        assert config.environment == Environment.DEVELOPMENT

    def test_from_dict_invalid_log_level(self) -> None:
        """Test handling invalid log level in dictionary."""
        data = {"logging": {"level": "INVALID"}}
        config = SDDConfig._from_dict(data)
        # Should fall back to default
        assert config.logging.level == LogLevel.INFO


class TestConfigFileIO:
    """Tests for configuration file I/O."""

    def test_save_and_load_yaml(self, tmp_path: Path) -> None:
        """Test saving and loading YAML configuration."""
        config = SDDConfig(environment=Environment.STAGING)
        config.server.port = 9000
        config.execution.max_parallel_roles = 5

        yaml_path = tmp_path / "config.yaml"
        config.save(yaml_path)

        assert yaml_path.exists()
        loaded = SDDConfig.from_file(yaml_path)
        assert loaded.environment == Environment.STAGING
        assert loaded.server.port == 9000
        assert loaded.execution.max_parallel_roles == 5

    def test_save_and_load_json(self, tmp_path: Path) -> None:
        """Test saving and loading JSON configuration."""
        config = SDDConfig()
        config.server.debug = True
        config.logging.level = LogLevel.DEBUG

        json_path = tmp_path / "config.json"
        config.save(json_path)

        assert json_path.exists()
        loaded = SDDConfig.from_file(json_path)
        assert loaded.server.debug is True
        assert loaded.logging.level == LogLevel.DEBUG

    def test_from_file_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent configuration file."""
        with pytest.raises(FileNotFoundError):
            SDDConfig.from_file(tmp_path / "nonexistent.yaml")

    def test_from_file_invalid_yaml(self, tmp_path: Path) -> None:
        """Test loading invalid YAML file."""
        yaml_path = tmp_path / "invalid.yaml"
        yaml_path.write_text("invalid: yaml: content: [")
        with pytest.raises(ValueError, match="Invalid YAML"):
            SDDConfig.from_file(yaml_path)

    def test_from_file_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON file."""
        json_path = tmp_path / "invalid.json"
        json_path.write_text("{invalid json}")
        with pytest.raises(ValueError, match="Invalid JSON"):
            SDDConfig.from_file(json_path)

    def test_from_file_unsupported_format(self, tmp_path: Path) -> None:
        """Test loading unsupported file format."""
        txt_path = tmp_path / "config.txt"
        txt_path.write_text("config data")
        with pytest.raises(ValueError, match="Unsupported config file format"):
            SDDConfig.from_file(txt_path)


class TestEnvironmentVariables:
    """Tests for environment variable loading."""

    def test_from_env_server_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading server config from environment variables."""
        monkeypatch.setenv("SDD_HOST", "0.0.0.0")
        monkeypatch.setenv("SDD_PORT", "9000")
        monkeypatch.setenv("SDD_DEBUG", "true")
        monkeypatch.setenv("SDD_WORKERS", "4")

        config = ServerConfig.from_env()
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.debug is True
        assert config.workers == 4

    def test_from_env_execution_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading execution config from environment variables."""
        monkeypatch.setenv("SDD_MAX_PARALLEL", "5")
        monkeypatch.setenv("SDD_ROLE_TIMEOUT", "1200.0")
        monkeypatch.setenv("SDD_STREAMING", "false")

        config = ExecutionConfig.from_env()
        assert config.max_parallel_roles == 5
        assert config.role_timeout_seconds == 1200.0
        assert config.enable_streaming is False

    def test_from_env_logging_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading logging config from environment variables."""
        monkeypatch.setenv("SDD_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("SDD_LOG_JSON", "true")

        config = LoggingConfig.from_env()
        assert config.level == LogLevel.DEBUG
        assert config.json_format is True

    def test_from_env_invalid_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test handling invalid log level from environment."""
        monkeypatch.setenv("SDD_LOG_LEVEL", "INVALID")

        config = LoggingConfig.from_env()
        # Should fall back to default
        assert config.level == LogLevel.INFO

    def test_from_env_plugin_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading plugin config from environment variables."""
        monkeypatch.setenv("SDD_PLUGIN_PATHS", "path1,path2")
        monkeypatch.setenv("SDD_ENABLED_PLUGINS", "architect,reviewer")
        monkeypatch.setenv("SDD_AUTO_DISCOVER", "false")

        config = PluginConfig.from_env()
        assert config.discovery_paths == ["path1", "path2"]
        assert config.enabled_plugins == ["architect", "reviewer"]
        assert config.auto_discover is False

    def test_from_env_security_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading security config from environment variables."""
        monkeypatch.setenv("SDD_RATE_LIMIT_REQUESTS", "50")
        monkeypatch.setenv("SDD_RATE_LIMIT_WINDOW", "30.0")
        monkeypatch.setenv("SDD_INPUT_VALIDATION", "false")

        config = SecurityConfig.from_env()
        assert config.rate_limit.requests_per_window == 50
        assert config.rate_limit.window_seconds == 30.0
        assert config.enable_input_validation is False

    def test_from_env_observability_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading observability config from environment variables."""
        monkeypatch.setenv("SDD_METRICS_PREFIX", "custom")
        monkeypatch.setenv("SDD_TRACING", "true")
        monkeypatch.setenv("SDD_AUDIT_ENABLED", "false")

        config = ObservabilityConfig.from_env()
        assert config.metrics.prefix == "custom"
        assert config.enable_tracing is True
        assert config.audit.enabled is False

    def test_from_env_full_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading full config from environment variables."""
        monkeypatch.setenv("SDD_ENV", "production")
        monkeypatch.setenv("SDD_PORT", "8080")
        monkeypatch.setenv("SDD_LOG_LEVEL", "WARNING")

        config = SDDConfig.from_env()
        assert config.environment == Environment.PRODUCTION
        assert config.server.port == 8080
        assert config.logging.level == LogLevel.WARNING


class TestGetConfig:
    """Tests for get_config function."""

    def setup_method(self) -> None:
        """Clear lru_cache before each test to avoid cross-test contamination."""
        get_config.cache_clear()

    def teardown_method(self) -> None:
        """Clear lru_cache after each test."""
        get_config.cache_clear()

    def test_get_config_returns_sdd_config(self) -> None:
        """Test that get_config returns SDDConfig instance."""
        config = get_config()
        assert isinstance(config, SDDConfig)

    def test_get_config_cached(self) -> None:
        """Test that get_config returns cached instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config(self) -> None:
        """Test that reload_config clears cache and returns fresh instance."""
        config1 = get_config()
        reloaded = reload_config()
        assert isinstance(reloaded, SDDConfig)
        # After reload the cache is populated with a new call
        config2 = get_config()
        assert isinstance(config2, SDDConfig)
        # The reloaded config should not be the same cached object as before reload
        assert config1 is not reloaded

    def test_get_config_uses_file_when_present(self, tmp_path: Path) -> None:
        """Test that get_config reads file config when the config file exists."""
        import sdd_server.infrastructure.config as config_module

        config_file = tmp_path / "config.yaml"
        config_file.write_text("environment: production\n")

        original = config_module.DEFAULT_CONFIG_FILE
        try:
            config_module.DEFAULT_CONFIG_FILE = config_file
            get_config.cache_clear()
            config = get_config()
            assert config.environment.value == "production"
        finally:
            config_module.DEFAULT_CONFIG_FILE = original
            get_config.cache_clear()

    def test_get_config_falls_back_to_env_when_no_file(self, tmp_path: Path) -> None:
        """Test that get_config returns env config when no file exists."""
        import sdd_server.infrastructure.config as config_module

        original = config_module.DEFAULT_CONFIG_FILE
        try:
            config_module.DEFAULT_CONFIG_FILE = tmp_path / "nonexistent.yaml"
            get_config.cache_clear()
            config = get_config()
            assert isinstance(config, SDDConfig)
        finally:
            config_module.DEFAULT_CONFIG_FILE = original
            get_config.cache_clear()

    def test_get_config_falls_back_on_invalid_file(self, tmp_path: Path) -> None:
        """Test that get_config falls back to env config when file is malformed."""
        import sdd_server.infrastructure.config as config_module

        config_file = tmp_path / "config.yaml"
        config_file.write_text("not: valid: yaml: [[[")

        original = config_module.DEFAULT_CONFIG_FILE
        try:
            config_module.DEFAULT_CONFIG_FILE = config_file
            get_config.cache_clear()
            config = get_config()
            # Should fall back gracefully
            assert isinstance(config, SDDConfig)
        finally:
            config_module.DEFAULT_CONFIG_FILE = original
            get_config.cache_clear()


class TestNestedSettings:
    """Tests for nested settings classes."""

    def test_retry_settings_defaults(self) -> None:
        """Test RetrySettings default values."""
        settings = RetrySettings()
        assert settings.max_retries == 3
        assert settings.initial_delay == 1.0
        assert settings.max_delay == 60.0
        assert settings.exponential_base == 2.0
        assert settings.jitter is True

    def test_rate_limit_settings_defaults(self) -> None:
        """Test RateLimitSettings default values."""
        settings = RateLimitSettings()
        assert settings.requests_per_window == 100
        assert settings.window_seconds == 60.0

    def test_metrics_settings_defaults(self) -> None:
        """Test MetricsSettings default values."""
        settings = MetricsSettings()
        assert settings.prefix == "sdd"
        assert settings.enable_default_metrics is True

    def test_health_check_settings_defaults(self) -> None:
        """Test HealthCheckSettings default values."""
        settings = HealthCheckSettings()
        assert settings.check_interval == 30.0

    def test_audit_settings_defaults(self) -> None:
        """Test AuditSettings default values."""
        settings = AuditSettings()
        assert settings.enabled is True
        assert settings.file_path is None

    def test_audit_settings_custom(self) -> None:
        """Test AuditSettings custom values."""
        settings = AuditSettings(enabled=False, file_path="/var/log/audit.log")
        assert settings.enabled is False
        assert settings.file_path == "/var/log/audit.log"
