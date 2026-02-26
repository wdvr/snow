import SwiftUI

/// Renders markdown content with proper formatting for AI chat responses.
/// Supports headers, bold/italic, bullet/numbered lists, code blocks, tables, and inline code.
struct MarkdownTextView: View {
    let text: String
    let foregroundColor: Color

    init(_ text: String, foregroundColor: Color = .primary) {
        self.text = text
        self.foregroundColor = foregroundColor
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(parseBlocks().enumerated()), id: \.offset) { _, block in
                blockView(block)
            }
        }
    }

    // MARK: - Block Types

    private enum MarkdownBlock {
        case paragraph(String)
        case header(level: Int, text: String)
        case codeBlock(language: String?, code: String)
        case bulletList([String])
        case numberedList([String])
        case table(headers: [String], rows: [[String]])
    }

    // MARK: - Block Rendering

    @ViewBuilder
    private func blockView(_ block: MarkdownBlock) -> some View {
        switch block {
        case .paragraph(let text):
            inlineMarkdown(text)

        case .header(let level, let text):
            Text(inlineAttributed(text))
                .font(headerFont(level))
                .fontWeight(.semibold)
                .foregroundStyle(foregroundColor)

        case .codeBlock(_, let code):
            Text(code)
                .font(.system(.caption, design: .monospaced))
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(.tertiarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 8))

        case .bulletList(let items):
            VStack(alignment: .leading, spacing: 4) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text("\u{2022}")
                            .foregroundStyle(foregroundColor.opacity(0.6))
                        inlineMarkdown(item)
                    }
                }
            }
            .padding(.leading, 4)

        case .numberedList(let items):
            VStack(alignment: .leading, spacing: 4) {
                ForEach(Array(items.enumerated()), id: \.offset) { index, item in
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text("\(index + 1).")
                            .foregroundStyle(foregroundColor.opacity(0.6))
                            .monospacedDigit()
                        inlineMarkdown(item)
                    }
                }
            }
            .padding(.leading, 4)

        case .table(let headers, let rows):
            tableView(headers: headers, rows: rows)
        }
    }

    private func headerFont(_ level: Int) -> Font {
        switch level {
        case 1: return .title3
        case 2: return .headline
        default: return .subheadline
        }
    }

    // MARK: - Table Rendering

    private func tableView(headers: [String], rows: [[String]]) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
                // Header row
                HStack(spacing: 0) {
                    ForEach(Array(headers.enumerated()), id: \.offset) { colIndex, header in
                        Text(inlineAttributed(header.trimmingCharacters(in: .whitespaces)))
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(foregroundColor)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 6)
                            .frame(minWidth: 60, alignment: .leading)
                        if colIndex < headers.count - 1 {
                            Divider()
                        }
                    }
                }
                .background(Color(.tertiarySystemBackground))

                Divider()

                // Data rows
                ForEach(Array(rows.enumerated()), id: \.offset) { rowIndex, row in
                    HStack(spacing: 0) {
                        ForEach(Array(row.enumerated()), id: \.offset) { colIndex, cell in
                            Text(inlineAttributed(cell.trimmingCharacters(in: .whitespaces)))
                                .font(.caption)
                                .foregroundStyle(foregroundColor)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 5)
                                .frame(minWidth: 60, alignment: .leading)
                            if colIndex < row.count - 1 {
                                Divider()
                            }
                        }
                    }
                    if rowIndex < rows.count - 1 {
                        Divider()
                    }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(Color(.separator).opacity(0.5), lineWidth: 0.5)
            )
        }
    }

    // MARK: - Inline Markdown Rendering

    private func inlineMarkdown(_ text: String) -> some View {
        Text(inlineAttributed(text))
            .foregroundStyle(foregroundColor)
    }

    /// Convert inline markdown (bold, italic, code, links) to AttributedString
    private func inlineAttributed(_ text: String) -> AttributedString {
        // Try SwiftUI's built-in markdown parsing
        if let attributed = try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)) {
            return attributed
        }
        return AttributedString(text)
    }

    // MARK: - Block Parser

    private func parseBlocks() -> [MarkdownBlock] {
        let lines = text.components(separatedBy: "\n")
        var blocks: [MarkdownBlock] = []
        var index = 0

        while index < lines.count {
            let line = lines[index]
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            // Skip empty lines
            if trimmed.isEmpty {
                index += 1
                continue
            }

            // Code block
            if trimmed.hasPrefix("```") {
                let language = String(trimmed.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                var codeLines: [String] = []
                index += 1
                while index < lines.count {
                    if lines[index].trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                        index += 1
                        break
                    }
                    codeLines.append(lines[index])
                    index += 1
                }
                blocks.append(.codeBlock(
                    language: language.isEmpty ? nil : language,
                    code: codeLines.joined(separator: "\n")
                ))
                continue
            }

            // Header
            if let (level, headerText) = parseHeader(trimmed) {
                blocks.append(.header(level: level, text: headerText))
                index += 1
                continue
            }

            // Table (lines starting with |)
            if isTableRow(trimmed) {
                var tableLines: [String] = []
                while index < lines.count {
                    let tableLine = lines[index].trimmingCharacters(in: .whitespaces)
                    if isTableRow(tableLine) || isTableSeparator(tableLine) {
                        tableLines.append(tableLine)
                        index += 1
                    } else {
                        break
                    }
                }
                if let table = parseTable(tableLines) {
                    blocks.append(table)
                }
                continue
            }

            // Bullet list
            if trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") || trimmed.hasPrefix("+ ") {
                var items: [String] = []
                while index < lines.count {
                    let listLine = lines[index].trimmingCharacters(in: .whitespaces)
                    if listLine.hasPrefix("- ") {
                        items.append(String(listLine.dropFirst(2)))
                    } else if listLine.hasPrefix("* ") {
                        items.append(String(listLine.dropFirst(2)))
                    } else if listLine.hasPrefix("+ ") {
                        items.append(String(listLine.dropFirst(2)))
                    } else if listLine.isEmpty {
                        index += 1
                        break
                    } else {
                        break
                    }
                    index += 1
                }
                blocks.append(.bulletList(items))
                continue
            }

            // Numbered list
            if isNumberedListItem(trimmed) {
                var items: [String] = []
                while index < lines.count {
                    let listLine = lines[index].trimmingCharacters(in: .whitespaces)
                    if let itemText = parseNumberedListItem(listLine) {
                        items.append(itemText)
                    } else if listLine.isEmpty {
                        index += 1
                        break
                    } else {
                        break
                    }
                    index += 1
                }
                blocks.append(.numberedList(items))
                continue
            }

            // Regular paragraph - collect consecutive non-empty, non-special lines
            var paragraphLines: [String] = []
            while index < lines.count {
                let paraLine = lines[index]
                let paraTrimmed = paraLine.trimmingCharacters(in: .whitespaces)
                if paraTrimmed.isEmpty
                    || paraTrimmed.hasPrefix("```")
                    || paraTrimmed.hasPrefix("# ")
                    || paraTrimmed.hasPrefix("## ")
                    || paraTrimmed.hasPrefix("### ")
                    || paraTrimmed.hasPrefix("- ")
                    || paraTrimmed.hasPrefix("* ")
                    || paraTrimmed.hasPrefix("+ ")
                    || isNumberedListItem(paraTrimmed)
                    || isTableRow(paraTrimmed) {
                    break
                }
                paragraphLines.append(paraTrimmed)
                index += 1
            }
            if !paragraphLines.isEmpty {
                blocks.append(.paragraph(paragraphLines.joined(separator: " ")))
            }
        }

        return blocks
    }

    // MARK: - Parsing Helpers

    /// Parse a header line like "## Title" → (level: 2, text: "Title")
    private func parseHeader(_ line: String) -> (Int, String)? {
        var level = 0
        var remaining = line[...]
        while remaining.hasPrefix("#") && level < 3 {
            remaining = remaining.dropFirst()
            level += 1
        }
        guard level > 0, remaining.hasPrefix(" ") else { return nil }
        let text = remaining.drop(while: { $0 == " " })
        guard !text.isEmpty else { return nil }
        return (level, String(text))
    }

    /// Check if a line starts with a numbered list pattern like "1. "
    private func isNumberedListItem(_ line: String) -> Bool {
        parseNumberedListItem(line) != nil
    }

    /// Parse a numbered list item like "1. Text" → "Text"
    private func parseNumberedListItem(_ line: String) -> String? {
        let chars = Array(line)
        var i = 0
        // Skip digits
        while i < chars.count && chars[i].isNumber {
            i += 1
        }
        guard i > 0, i < chars.count, chars[i] == "." else { return nil }
        i += 1
        guard i < chars.count, chars[i] == " " else { return nil }
        i += 1
        // Skip leading spaces
        while i < chars.count && chars[i] == " " {
            i += 1
        }
        return String(chars[i...])
    }

    /// Check if a line looks like a markdown table row: starts and ends with |
    private func isTableRow(_ line: String) -> Bool {
        line.hasPrefix("|") && line.hasSuffix("|") && line.contains(" ")
    }

    /// Check if a line is a table separator like |---|---|
    private func isTableSeparator(_ line: String) -> Bool {
        guard line.hasPrefix("|") else { return false }
        let cleaned = line.replacingOccurrences(of: "|", with: "")
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: ":", with: "")
            .trimmingCharacters(in: .whitespaces)
        return cleaned.isEmpty
    }

    /// Parse collected table lines into a table block
    private func parseTable(_ lines: [String]) -> MarkdownBlock? {
        // Filter out separator lines
        let dataLines = lines.filter { !isTableSeparator($0) }
        guard dataLines.count >= 2 else {
            // Need at least header + 1 data row
            if dataLines.count == 1 {
                let headers = parseTableCells(dataLines[0])
                return .table(headers: headers, rows: [])
            }
            return nil
        }

        let headers = parseTableCells(dataLines[0])
        let rows = dataLines.dropFirst().map { parseTableCells($0) }
        return .table(headers: headers, rows: Array(rows))
    }

    /// Split "| cell1 | cell2 | cell3 |" into ["cell1", "cell2", "cell3"]
    private func parseTableCells(_ line: String) -> [String] {
        var cells = line.components(separatedBy: "|")
        // Remove empty first and last elements from leading/trailing pipes
        if cells.first?.trimmingCharacters(in: .whitespaces).isEmpty == true {
            cells.removeFirst()
        }
        if cells.last?.trimmingCharacters(in: .whitespaces).isEmpty == true {
            cells.removeLast()
        }
        return cells
    }
}
