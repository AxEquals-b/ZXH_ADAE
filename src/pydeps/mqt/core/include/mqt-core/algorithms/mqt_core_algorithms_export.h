
#ifndef MQT_CORE_ALGORITHMS_EXPORT_H
#define MQT_CORE_ALGORITHMS_EXPORT_H

#ifdef MQT_CORE_ALGORITHMS_STATIC_DEFINE
#  define MQT_CORE_ALGORITHMS_EXPORT
#  define MQT_CORE_ALGORITHMS_NO_EXPORT
#else
#  ifndef MQT_CORE_ALGORITHMS_EXPORT
#    ifdef mqt_core_algorithms_EXPORTS
        /* We are building this library */
#      define MQT_CORE_ALGORITHMS_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define MQT_CORE_ALGORITHMS_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef MQT_CORE_ALGORITHMS_NO_EXPORT
#    define MQT_CORE_ALGORITHMS_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef MQT_CORE_ALGORITHMS_DEPRECATED
#  define MQT_CORE_ALGORITHMS_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef MQT_CORE_ALGORITHMS_DEPRECATED_EXPORT
#  define MQT_CORE_ALGORITHMS_DEPRECATED_EXPORT MQT_CORE_ALGORITHMS_EXPORT MQT_CORE_ALGORITHMS_DEPRECATED
#endif

#ifndef MQT_CORE_ALGORITHMS_DEPRECATED_NO_EXPORT
#  define MQT_CORE_ALGORITHMS_DEPRECATED_NO_EXPORT MQT_CORE_ALGORITHMS_NO_EXPORT MQT_CORE_ALGORITHMS_DEPRECATED
#endif

/* NOLINTNEXTLINE(readability-avoid-unconditional-preprocessor-if) */
#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef MQT_CORE_ALGORITHMS_NO_DEPRECATED
#    define MQT_CORE_ALGORITHMS_NO_DEPRECATED
#  endif
#endif

#endif /* MQT_CORE_ALGORITHMS_EXPORT_H */
