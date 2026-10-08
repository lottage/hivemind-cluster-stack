package dev.stonesage.watch

import org.json.JSONArray
import org.json.JSONObject

/** JSON -> Map/List for the Connect IQ SDK (nulls dropped; Monkey C sees Dictionary/Array). */
fun JSONObject.toNative(): Map<String, Any> {
    val out = LinkedHashMap<String, Any>()
    for (key in keys()) toNativeValue(opt(key))?.let { out[key] = it }
    return out
}

private fun toNativeValue(v: Any?): Any? = when (v) {
    null, JSONObject.NULL -> null
    is JSONObject -> v.toNative()
    is JSONArray -> (0 until v.length()).mapNotNull { toNativeValue(v.opt(it)) }
    is Long -> if (v in Int.MIN_VALUE..Int.MAX_VALUE) v.toInt() else v
    else -> v
}

/** Map/List from the watch -> JSON for the bridge. */
fun nativeToJson(v: Any?): Any = when (v) {
    null -> JSONObject.NULL
    is Map<*, *> -> JSONObject().apply { v.forEach { (k, x) -> put(k.toString(), nativeToJson(x)) } }
    is List<*> -> JSONArray().apply { v.forEach { put(nativeToJson(it)) } }
    else -> v
}
