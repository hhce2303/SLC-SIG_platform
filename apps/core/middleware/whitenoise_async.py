"""
WhiteNoise async-capable.

WhiteNoiseMiddleware (incluso 6.8) es sync-only. Bajo ASGI, un middleware
sync-only en la cadena obliga a Django a adaptar las respuestas async a sync,
lo que **consume y bufferiza** los StreamingHttpResponse con generador async
(los eventos SSE solo se sueltan al cerrar la conexión).

Este wrapper declara async_capable y:
  - Sirve archivos estáticos por la vía sync de WhiteNoise (envuelta en un
    thread, sin bloquear el event loop).
  - Para cualquier otra ruta (API, SSE) hace `await self.get_response(request)`
    directo → el stream queda 100% async y flushea evento por evento.

Usa solo API estable de WhiteNoise 6.x: self.autorefresh, self.files,
self.find_file(), self.serve().
"""

from __future__ import annotations

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from whitenoise.middleware import WhiteNoiseMiddleware


class AsyncWhiteNoiseMiddleware(WhiteNoiseMiddleware):
    async_capable = True
    sync_capable = True

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)
        # Vía sync original de WhiteNoise (sin cambios de comportamiento).
        return super().__call__(request)

    async def __acall__(self, request):
        # Lookup del archivo estático (dict en prod; I/O solo en autorefresh/dev).
        if self.autorefresh:
            static_file = await sync_to_async(self.find_file)(request.path_info)
        else:
            static_file = self.files.get(request.path_info)

        if static_file is not None:
            # Es un estático → servir por la vía sync de WhiteNoise en un thread.
            return await sync_to_async(self.serve)(static_file, request)

        # No es estático (API / SSE) → cadena async pura, sin buffering.
        return await self.get_response(request)
