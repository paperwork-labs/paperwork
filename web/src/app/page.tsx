export default function Home() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        fontFamily: "system-ui, sans-serif",
        background: "#0a0a0a",
        color: "#fafafa",
      }}
    >
      <h1 style={{ fontSize: "3rem", fontWeight: 700, marginBottom: "0.5rem" }}>
        FileFree
      </h1>
      <p style={{ fontSize: "1.25rem", color: "#a1a1aa" }}>
        Free AI-powered tax filing for Gen Z
      </p>
      <p
        style={{ fontSize: "0.875rem", color: "#52525b", marginTop: "2rem" }}
      >
        Dev environment running on localhost:3000
      </p>
    </main>
  );
}
