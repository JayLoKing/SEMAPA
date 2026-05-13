"""Configuración centralizada desde variables de entorno."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Cassandra
    CASSANDRA_HOSTS: str = "cassandra-1,cassandra-2"
    CASSANDRA_PORT: int = 9042
    CASSANDRA_KEYSPACE: str = "semapa"
    CASSANDRA_USER: str = "cassandra"
    CASSANDRA_PASSWORD: str = "cassandra"
    CASSANDRA_DC: str = "datacenter1"

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "semapa"
    RABBITMQ_PASSWORD: str = "semapa"
    RABBITMQ_VHOST: str = "/"

    # JWT
    JWT_SECRET: str = "change_me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MIN: int = 720

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 2
    API_LOG_LEVEL: str = "INFO"
    API_CORS_ORIGINS: str = "http://localhost,http://localhost:5173"

    # USD (apilayer.exchangerate.host)
    USD_API_URL: str = "https://api.exchangerate.host/live?source=USD&currencies=BOB"
    USD_API_KEY: str = ""
    USD_CACHE_TTL: int = 900
    USD_FALLBACK_RATE: float = 6.96


settings = Settings()
