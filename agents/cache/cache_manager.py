import os
import json
import hashlib
import time
from pathlib import Path
from slais import config
from slais.utils.logging_utils import logger

class CacheManager:
    def __init__(self):
        self.cache_dir = Path(config.settings.CACHE_DIR)
        self.cache_expiry_seconds = config.settings.CACHE_EXPIRY_DAYS * 24 * 3600
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CacheManager initialized. Cache directory: {self.cache_dir}, Expiry: {config.settings.CACHE_EXPIRY_DAYS} days")

    def _get_cache_filepath(self, key: str) -> Path:
        """Generates a cache file path based on the key."""
        # Use SHA256 hash of the key as the filename
        key_hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    def get(self, key: str) -> any:
        """
        Retrieves data from cache if not expired.

        Args:
            key: The cache key (e.g., a prompt string or a unique identifier).

        Returns:
            Cached data if valid and not expired, otherwise None.
        """
        filepath = self._get_cache_filepath(key)
        if not filepath.exists():
            logger.debug(f"Cache miss for key: {key[:50]}...")
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            timestamp = cache_data.get("timestamp")
            data = cache_data.get("data")

            if timestamp is None or data is None:
                logger.warning(f"Invalid cache data in file: {filepath}. Deleting.")
                filepath.unlink(missing_ok=True)
                return None

            # Check for expiry
            if time.time() - timestamp > self.cache_expiry_seconds:
                logger.info(f"Cache expired for key: {key[:50]}... File: {filepath}. Deleting.")
                filepath.unlink(missing_ok=True)
                return None

            logger.debug(f"Cache hit for key: {key[:50]}...")
            return data

        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error reading or parsing cache file {filepath}: {e}. Deleting.")
            filepath.unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.exception(f"Unexpected error in CacheManager.get for file {filepath}: {e}")
            filepath.unlink(missing_ok=True)
            return None

    def set(self, key: str, value: any) -> None:
        """
        Saves data to cache.

        Args:
            key: The cache key.
            value: The data to cache.
        """
        filepath = self._get_cache_filepath(key)
        cache_data = {
            "timestamp": time.time(),
            "data": value
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cache set for key: {key[:50]}... File: {filepath}")
        except IOError as e:
            logger.error(f"Error writing cache file {filepath}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error in CacheManager.set for file {filepath}: {e}")

    def clear_expired(self) -> None:
        """Clears all expired cache files."""
        logger.info("Starting to clear expired cache files...")
        now = time.time()
        deleted_count = 0
        try:
            for filepath in self.cache_dir.iterdir():
                if filepath.is_file() and filepath.suffix == '.json':
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        timestamp = cache_data.get("timestamp")
                        if timestamp is not None and now - timestamp > self.cache_expiry_seconds:
                            filepath.unlink(missing_ok=True)
                            deleted_count += 1
                            logger.debug(f"Cleared expired cache file: {filepath}")
                    except (IOError, json.JSONDecodeError) as e:
                        logger.warning(f"Could not read or parse cache file {filepath} during cleanup: {e}. Deleting.")
                        filepath.unlink(missing_ok=True)
                        deleted_count += 1
                    except Exception as e:
                        logger.exception(f"Unexpected error during cache cleanup for file {filepath}: {e}. Deleting.")
                        filepath.unlink(missing_ok=True)
                        deleted_count += 1
        except Exception as e:
            logger.error(f"Error during cache directory iteration: {e}")

        logger.info(f"Finished clearing expired cache files. Deleted {deleted_count} files.")

# Optional: Instantiate a global cache manager or create instances as needed
# cache_manager = CacheManager()
