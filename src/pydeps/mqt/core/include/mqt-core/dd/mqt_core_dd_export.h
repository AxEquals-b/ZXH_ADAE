
#ifndef MQT_CORE_DD_EXPORT_H
#define MQT_CORE_DD_EXPORT_H

#ifdef MQT_CORE_DD_STATIC_DEFINE
#  define MQT_CORE_DD_EXPORT
#  define MQT_CORE_DD_NO_EXPORT
#else
#  ifndef MQT_CORE_DD_EXPORT
#    ifdef mqt_core_dd_EXPORTS
        /* We are building this library */
#      define MQT_CORE_DD_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define MQT_CORE_DD_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef MQT_CORE_DD_NO_EXPORT
#    define MQT_CORE_DD_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef MQT_CORE_DD_DEPRECATED
#  define MQT_CORE_DD_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef MQT_CORE_DD_DEPRECATED_EXPORT
#  define MQT_CORE_DD_DEPRECATED_EXPORT MQT_CORE_DD_EXPORT MQT_CORE_DD_DEPRECATED
#endif

#ifndef MQT_CORE_DD_DEPRECATED_NO_EXPORT
#  define MQT_CORE_DD_DEPRECATED_NO_EXPORT MQT_CORE_DD_NO_EXPORT MQT_CORE_DD_DEPRECATED
#endif

/* NOLINTNEXTLINE(readability-avoid-unconditional-preprocessor-if) */
#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef MQT_CORE_DD_NO_DEPRECATED
#    define MQT_CORE_DD_NO_DEPRECATED
#  endif
#endif

#endif /* MQT_CORE_DD_EXPORT_H */
