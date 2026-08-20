import Foundation

struct RemoteRequest: Codable {
    let protocolName: String
    let requestID: String
    let operation: String
    let params: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case protocolName = "protocol"
        case requestID = "request_id"
        case operation
        case params
    }
}

enum JSONValue: Codable {
    case string(String)
    case bool(Bool)
    case number(Double)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null; return }
        if let value = try? container.decode(Bool.self) { self = .bool(value); return }
        if let value = try? container.decode(Double.self) { self = .number(value); return }
        if let value = try? container.decode(String.self) { self = .string(value); return }
        if let value = try? container.decode([String: JSONValue].self) { self = .object(value); return }
        if let value = try? container.decode([JSONValue].self) { self = .array(value); return }
        throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value")
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}

actor ControlClient {
    func call(endpoint: URL, token: String, operation: String, params: [String: JSONValue]) async throws -> String {
        guard endpoint.scheme?.lowercased() == "https" else {
            throw URLError(.secureConnectionFailed)
        }
        var url = endpoint
        if !url.path.hasSuffix("/v1/agent") {
            url.append(path: "v1/agent")
        }
        let envelope = RemoteRequest(
            protocolName: "qsol-control-remote-request/1",
            requestID: UUID().uuidString,
            operation: operation,
            params: params
        )
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(envelope)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return String(decoding: data, as: UTF8.self)
    }
}
