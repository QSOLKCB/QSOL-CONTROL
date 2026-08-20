package org.qsol.control

import org.json.JSONObject
import java.net.URL
import java.util.UUID
import javax.net.ssl.HttpsURLConnection

class ControlClient {
    fun call(endpoint: String, token: String, operation: String, params: JSONObject): String {
        val base = endpoint.trimEnd('/')
        require(base.startsWith("https://")) { "HTTPS endpoint required" }
        val url = URL("$base/v1/agent")
        val envelope = JSONObject()
            .put("protocol", "qsol-control-remote-request/1")
            .put("request_id", UUID.randomUUID().toString())
            .put("operation", operation)
            .put("params", params)
        val connection = (url.openConnection() as HttpsURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 15_000
            readTimeout = 30_000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Authorization", "Bearer $token")
        }
        connection.outputStream.use { output ->
            output.write(envelope.toString().toByteArray(Charsets.UTF_8))
        }
        val stream = if (connection.responseCode == 200) connection.inputStream else connection.errorStream
        val body = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
        if (connection.responseCode != 200) {
            throw IllegalStateException("Gateway HTTP ${connection.responseCode}: $body")
        }
        return body
    }
}
