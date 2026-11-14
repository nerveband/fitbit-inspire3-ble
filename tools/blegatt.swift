// Interact with the Inspire 3 from the Mac: enumerate, read, subscribe, and poke GattLink.
// Build: swiftc -O blegatt.swift -o blegatt
// Run:   ./blegatt [nameSubstring] [scanSeconds] [listenSeconds]
import Foundation
import CoreBluetooth

func hexs(_ d: Data) -> String { d.map { String(format: "%02x", $0) }.joined() }

let want = CommandLine.arguments.count > 1 ? CommandLine.arguments[1].lowercased() : "inspire"
let scanSecs = CommandLine.arguments.count > 2 ? Double(CommandLine.arguments[2])! : 12.0
let listenSecs = CommandLine.arguments.count > 3 ? Double(CommandLine.arguments[3])! : 15.0

// Fitbit GattLink data pair seen on this device, plus the SLS-ish service
let WRITE_UUID = CBUUID(string: "ABBAFF01-E56A-484C-B832-8B17CF6CBFE8")
let NOTIFY_UUID = CBUUID(string: "ABBAFF02-E56A-484C-B832-8B17CF6CBFE8")

final class Tool: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    var central: CBCentralManager!
    var seen: [(CBPeripheral, Int, [String])] = []
    var dev: CBPeripheral?
    var writeChar: CBCharacteristic?
    var notifyChar: CBCharacteristic?
    var notifications = 0

    func start() { central = CBCentralManager(delegate: self, queue: nil) }

    func centralManagerDidUpdateState(_ c: CBCentralManager) {
        guard c.state == .poweredOn else { print("adapter state \(c.state.rawValue)"); return }
        print("scanning \(scanSecs)s for \(want)")
        c.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral,
                        advertisementData d: [String: Any], rssi RSSI: NSNumber) {
        var svcs: [String] = []
        if let u = d[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID] { svcs = u.map { $0.uuidString } }
        if seen.contains(where: { $0.0.identifier == p.identifier }) { return }
        seen.append((p, RSSI.intValue, svcs))
    }

    func centralManager(_ c: CBCentralManager, didConnect p: CBPeripheral) {
        print("connected: \(p.name ?? "?")")
        p.discoverServices(nil)
    }

    func centralManager(_ c: CBCentralManager, didDisconnectPeripheral p: CBPeripheral, error: Error?) {
        print("disconnected: \(error?.localizedDescription ?? "clean")")
    }

    func centralManager(_ c: CBCentralManager, didFailToConnect p: CBPeripheral, error: Error?) {
        print("connect failed: \(error?.localizedDescription ?? "?")")
    }

    func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        print("\n=== services ===")
        for s in p.services ?? [] {
            print("\(s.uuid.uuidString)")
            p.discoverCharacteristics(nil, for: s)
        }
    }

    func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor s: CBService, error: Error?) {
        for ch in s.characteristics ?? [] {
            print("  \(s.uuid.uuidString) char \(ch.uuid.uuidString) props=0x\(String(ch.properties.rawValue, radix: 16))")
            if ch.properties.contains(.read) { p.readValue(for: ch) }
            if ch.properties.contains(.write) || ch.properties.contains(.writeWithoutResponse) {
                probeChars.append((ch, s.uuid.uuidString.prefix(6) + ""))
            }
            if ch.properties.contains(.notify) && ch.uuid != NOTIFY_UUID {
                p.setNotifyValue(true, for: ch)
            }
            if ch.uuid == NOTIFY_UUID {
                notifyChar = ch
                p.setNotifyValue(true, for: ch)
                print("    -> subscribed to notify")
            }
            if ch.uuid == WRITE_UUID { writeChar = ch; print("    -> write characteristic found") }
        }
    }

    func peripheral(_ p: CBPeripheral, didUpdateNotificationStateFor ch: CBCharacteristic, error: Error?) {
        if let e = error { print("notify state error on \(ch.uuid.uuidString): \(e.localizedDescription)") }
        else { print("notify \(ch.isNotifying ? "enabled" : "disabled") on \(ch.uuid.uuidString)") }
    }

    func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic, error: Error?) {
        if let e = error { print("value error \(ch.uuid.uuidString): \(e.localizedDescription)"); return }
        guard let v = ch.value else { return }
        let ascii = String(data: v, encoding: .utf8) ?? ""
        if ch.uuid == NOTIFY_UUID {
            notifications += 1
            if notifications <= 12 {
                print("NOTIFY[\(notifications)] len=\(v.count) \(hexs(v.prefix(40))) \(ascii.isEmpty ? "" : "|\(ascii.prefix(30))|")")
            }
        } else {
            print("read \(ch.uuid.uuidString) = \(hexs(v)) \(ascii.isEmpty ? "" : "|\(ascii.prefix(40))|")")
        }
    }

    func peripheral(_ p: CBPeripheral, didWriteValueFor ch: CBCharacteristic, error: Error?) {
        if let e = error { print("write error on \(ch.uuid.uuidString): \(e.localizedDescription)") }
    }

    func fireGattlinkReset() {
        guard let p = dev, let ch = writeChar else { print("no write char yet"); return }
        let resetRequest = Data([0x80])
        print("\n-> writing GattLink RESET_REQUEST (0x80) to \(ch.uuid.uuidString)")
        p.writeValue(resetRequest, for: ch, type: .withoutResponse)
    }

    var probeChars: [(CBCharacteristic, String)] = []

    func probeWrites() {
        guard let p = dev else { return }
        for (ch, label) in probeChars {
            let val = Data([0x00])
            let useResp = ch.properties.contains(.write)
            print("-> probe write \(label) \(ch.uuid.uuidString) props=0x\(String(ch.properties.rawValue, radix: 16)) withResponse=\(useResp) value=00")
            p.writeValue(val, for: ch, type: useResp ? .withResponse : .withoutResponse)
        }
    }

    func dump() {
        print("\n--- peripherals: \(seen.count) ---")
        for (p, r, s) in seen.sorted(by: { $0.1 > $1.1 }) where !(p.name ?? "").isEmpty || !s.isEmpty {
            print("  \(p.name ?? "-") rssi=\(r) svc=\(s.joined(separator: ","))")
        }
    }
}

let t = Tool()
t.start()
RunLoop.current.run(until: Date().addingTimeInterval(scanSecs))
t.central.stopScan()

var match: CBPeripheral?
for (p, r, svcs) in t.seen.sorted(by: { $0.1 > $1.1 }) {
    let n = (p.name ?? "").lowercased()
    if n.contains(want) || svcs.contains(where: { $0.uppercased() == "FD62" }) {
        print("target: \(p.name ?? "-") rssi=\(r) svc=\(svcs)")
        match = p
        break
    }
}
guard let m = match else { t.dump(); exit(1) }
t.dev = m
m.delegate = t
t.central.connect(m, options: nil)

RunLoop.current.run(until: Date().addingTimeInterval(6))
t.fireGattlinkReset()
RunLoop.current.run(until: Date().addingTimeInterval(3))
t.probeWrites()
RunLoop.current.run(until: Date().addingTimeInterval(listenSecs))
print("\nnotifications received: \(t.notifications)")
