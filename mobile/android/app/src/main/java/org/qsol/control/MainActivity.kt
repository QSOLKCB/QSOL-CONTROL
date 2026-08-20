package org.qsol.control

import android.app.Activity
import android.os.Bundle
import android.text.InputType
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val endpoint = EditText(this).apply {
            hint = "https://control.example"
            setText("https://control.example")
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        }
        val token = EditText(this).apply {
            hint = "Bearer token (memory only)"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val question = EditText(this).apply {
            hint = "Question"
            minLines = 4
        }
        val response = TextView(this).apply {
            text = "No response yet."
            setTextIsSelectable(true)
        }
        val button = Button(this).apply { text = "Ask evidence only" }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val params = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
            addView(endpoint, params)
            addView(token, params)
            addView(question, params)
            addView(button, params)
            addView(response, params)
        }
        setContentView(ScrollView(this).apply { addView(content) })

        button.setOnClickListener {
            val endpointValue = endpoint.text.toString()
            val tokenValue = token.text.toString()
            val questionValue = question.text.toString().trim()
            if (tokenValue.isBlank() || questionValue.isBlank()) {
                response.text = "Token and question are required."
                return@setOnClickListener
            }
            button.isEnabled = false
            executor.execute {
                val result = try {
                    ControlClient().call(
                        endpointValue,
                        tokenValue,
                        "control.ask",
                        JSONObject()
                            .put("question", questionValue)
                            .put("mode", "evidence_only")
                            .put("file_ids", org.json.JSONArray())
                    )
                } catch (error: Exception) {
                    "Request failed: ${error.message}"
                }
                runOnUiThread {
                    response.text = result
                    button.isEnabled = true
                }
            }
        }
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
