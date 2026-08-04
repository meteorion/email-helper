"""分类缓存管理器模块

基于注入的 cache_repo（需提供 get_classify_cache / set_classify_cache /
cleanup_expired_classify_cache 方法）实现分类结果的读写与清理。
"""

from src.core.logger import get_logger

logger = get_logger("ai.cache_manager")


class ClassifyCacheManager:
    """分类缓存管理器，封装 cache_repo 的缓存读写"""

    def __init__(self, cache_repo: object) -> None:
        """初始化缓存管理器

        Args:
            cache_repo: 缓存仓储对象，需实现：
                - get_classify_cache(mail_hash: str) -> dict | None
                - set_classify_cache(mail_hash: str, result: dict, ttl_hours: int) -> None
                - cleanup_expired_classify_cache() -> int
        """
        self._repo = cache_repo

    def get(self, mail_hash: str) -> dict | None:
        """根据邮件哈希获取缓存的分类结果

        Args:
            mail_hash: 邮件内容哈希

        Returns:
            命中返回分类结果 dict，未命中返回 None
        """
        try:
            return self._repo.get_classify_cache(mail_hash)  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning(f"读取分类缓存失败 (hash={mail_hash}): {e}")
            return None

    def set(self, mail_hash: str, result: dict, ttl_hours: int = 24) -> None:
        """写入分类结果缓存

        Args:
            mail_hash: 邮件内容哈希
            result: 分类结果 dict
            ttl_hours: 缓存有效期（小时），默认 24
        """
        try:
            self._repo.set_classify_cache(mail_hash, result, ttl_hours)  # type: ignore[attr-defined]
            logger.debug(f"写入分类缓存: hash={mail_hash}, ttl={ttl_hours}h")
        except Exception as e:
            logger.warning(f"写入分类缓存失败 (hash={mail_hash}): {e}")

    def cleanup(self) -> int:
        """清理过期缓存

        Returns:
            清理的缓存条数
        """
        try:
            count = self._repo.cleanup_expired_classify_cache()  # type: ignore[attr-defined]
            if count:
                logger.info(f"清理过期分类缓存 {count} 条")
            return count
        except Exception as e:
            logger.warning(f"清理分类缓存失败: {e}")
            return 0
