import SwiftUI

struct ContentView: View {
    @State private var endpoint = "https://control.example"
    @State private var token = ""
    @State private var question = ""
    @State private var response = ""
    @State private var running = false

    private let client = ControlClient()

    var body: some View {
        NavigationStack {
            Form {
                Section("Remote CONTROL") {
                    TextField("HTTPS endpoint", text: $endpoint)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("Bearer token (memory only)", text: $token)
                    TextEditor(text: $question)
                        .frame(minHeight: 120)
                    Button(running ? "Running…" : "Ask evidence only") {
                        Task { await ask() }
                    }
                    .disabled(running || token.isEmpty || question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                Section("Protocol response") {
                    Text(response.isEmpty ? "No response yet." : response)
                        .font(.system(.footnote, design: .monospaced))
                        .textSelection(.enabled)
                }
            }
            .navigationTitle("QSOL CONTROL")
        }
    }

    @MainActor
    private func ask() async {
        running = true
        defer { running = false }
        guard let url = URL(string: endpoint) else {
            response = "Invalid endpoint URL"
            return
        }
        do {
            response = try await client.call(
                endpoint: url,
                token: token,
                operation: "control.ask",
                params: [
                    "question": .string(question),
                    "mode": .string("evidence_only"),
                    "file_ids": .array([])
                ]
            )
        } catch {
            response = "Request failed: \(error.localizedDescription)"
        }
    }
}
