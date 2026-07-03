import logging

def patch_webrtc_asyncio():
    """
    Patches aioice and asyncio datagram transport to prevent:
    1) AttributeError: 'NoneType' object has no attribute 'sendto'
    2) AttributeError: 'NoneType' object has no attribute 'call_exception_handler'

    These exceptions occur in aiortc / aioice when STUN/TURN transaction retry timers
    fire after the underlying asyncio socket or event loop has already been closed
    during a Streamlit rerun, WebRTC stream termination, or connection timeout.
    """
    try:
        import aioice.ice
        import aioice.stun

        # 1. Patch aioice.ice.Connection.send_stun
        orig_send_stun = getattr(aioice.ice.Connection, "send_stun", None)
        if orig_send_stun and not getattr(orig_send_stun, "_is_patched", False):
            def safe_send_stun(self, message, addr):
                transport = getattr(self, "transport", None)
                if transport is None:
                    return
                if getattr(transport, "_sock", None) is None:
                    return
                if hasattr(transport, "is_closing") and transport.is_closing():
                    return
                try:
                    return orig_send_stun(self, message, addr)
                except (AttributeError, RuntimeError, OSError, ValueError):
                    pass
            safe_send_stun._is_patched = True
            aioice.ice.Connection.send_stun = safe_send_stun
            logging.debug("[WebRTCPatch] Applied patch to aioice.ice.Connection.send_stun")

        # 2. Patch aioice.stun.Transaction.__retry (mangled as _Transaction__retry)
        retry_attr = "_Transaction__retry" if hasattr(aioice.stun.Transaction, "_Transaction__retry") else "__retry"
        orig_retry = getattr(aioice.stun.Transaction, retry_attr, None)
        if orig_retry and not getattr(orig_retry, "_is_patched", False):
            def safe_retry(self, *args, **kwargs):
                protocol = getattr(self, "_Transaction__protocol", None) or getattr(self, "__protocol", None)
                if protocol is None:
                    return
                transport = getattr(protocol, "transport", None)
                if transport is None or getattr(transport, "_sock", None) is None or (hasattr(transport, "is_closing") and transport.is_closing()):
                    timer = getattr(self, "_Transaction__timer", None) or getattr(self, "__timer", None)
                    if timer and hasattr(timer, "cancel"):
                        try:
                            timer.cancel()
                        except Exception:
                            pass
                    return
                try:
                    return orig_retry(self, *args, **kwargs)
                except (AttributeError, RuntimeError, OSError, ValueError):
                    pass
            safe_retry._is_patched = True
            setattr(aioice.stun.Transaction, retry_attr, safe_retry)
            logging.debug("[WebRTCPatch] Applied patch to aioice.stun.Transaction.__retry")

        # 3. Patch asyncio _SelectorDatagramTransport._fatal_error and sendto as safety nets
        try:
            import asyncio.selector_events
            if hasattr(asyncio.selector_events, "_SelectorDatagramTransport"):
                transport_cls = asyncio.selector_events._SelectorDatagramTransport
                
                orig_sendto = getattr(transport_cls, "sendto", None)
                if orig_sendto and not getattr(orig_sendto, "_is_patched", False):
                    def safe_sendto(self, data, addr):
                        if getattr(self, "_sock", None) is None or getattr(self, "_closed", False):
                            return
                        try:
                            return orig_sendto(self, data, addr)
                        except (AttributeError, RuntimeError, OSError, ValueError):
                            pass
                    safe_sendto._is_patched = True
                    transport_cls.sendto = safe_sendto

                orig_fatal_error = getattr(transport_cls, "_fatal_error", None)
                if orig_fatal_error and not getattr(orig_fatal_error, "_is_patched", False):
                    def safe_fatal_error(self, exc, message="Fatal error on transport"):
                        if getattr(self, "_loop", None) is None or getattr(self, "_closed", False):
                            return
                        try:
                            return orig_fatal_error(self, exc, message)
                        except (AttributeError, RuntimeError):
                            pass
                    safe_fatal_error._is_patched = True
                    transport_cls._fatal_error = safe_fatal_error

                logging.debug("[WebRTCPatch] Applied patch to asyncio datagram transport")
        except Exception as e:
            logging.debug(f"[WebRTCPatch] Could not patch asyncio datagram transport: {e}")

    except ImportError as e:
        logging.debug(f"[WebRTCPatch] aioice not available for patching: {e}")
    except Exception as e:
        logging.warning(f"[WebRTCPatch] Error applying WebRTC asyncio patch: {e}")
