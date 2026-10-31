/**
 * Backend API for Your-Own-AI.
 * Serves the in-memory vector database over HTTP with cpp-httplib, using Ollama
 * for embeddings and answers.
 */
#ifdef _WIN32
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif
#include "httplib.h"
#include "vector_engine.h"
#include <algorithm>
#include <chrono>
#include <climits>
#include <cmath>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <queue>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;
void cors(httplib::Response &res) {
  res.set_header("Access-Control-Allow-Origin", "http://localhost:8080");
  res.set_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");
  res.set_header("Access-Control-Allow-Headers", "Content-Type");
}

class OllamaClient {
  string host;
  int port;
  string esc(const string &s) {
    string o;
    for (char c : s) {
      if (c == '"')
        o += "\\\"";
      else if (c == '\\')
        o += "\\\\";
      else if (c == '\n')
        o += "\\n";
      else if (c == '\r')
        o += "\\r";
      else if (c == '\t')
        o += "\\t";
      else
        o += c;
    }
    return o;
  }
  vector<float> parseEmbedding(const string &body) {
    size_t p = body.find("\"embedding\"");
    if (p == string::npos)
      return {};
    p = body.find('[', p);
    if (p == string::npos)
      return {};
    size_t e = p + 1, depth = 1;
    while (e < body.size() && depth > 0) {
      if (body[e] == '[')
        depth++;
      else if (body[e] == ']')
        depth--;
      e++;
    }
    return parseVec(body.substr(p + 1, e - p - 2));
  }
  string parseResponse(const string &body) {
    return extractStr(body, "response");
  }

public:
  string embedModel = "nomic-embed-text";
  string genModel = "llama3.2:1b";
  OllamaClient(const string &h = "127.0.0.1", int p = 11434)
      : host(h), port(p) {}
  bool isAvailable() {
    httplib::Client cli(host, port);
    cli.set_connection_timeout(2, 0);
    auto res = cli.Get("/api/tags");
    return res && res->status == 200;
  }
  vector<float> embed(const string &text) {
    httplib::Client cli(host, port);
    cli.set_connection_timeout(3, 0);
    cli.set_read_timeout(30, 0);
    string body =
        "{\"model\":\"" + embedModel + "\",\"prompt\":\"" + esc(text) + "\"}";
    auto res = cli.Post("/api/embeddings", body, "application/json");
    if (!res || res->status != 200)
      return {};
    return parseEmbedding(res->body);
  }
  string generate(const string &prompt) {
    httplib::Client cli(host, port);
    cli.set_connection_timeout(3, 0);
    cli.set_read_timeout(180, 0);
    string body = "{\"model\":\"" + genModel +
                       "\","
                       "\"prompt\":\"" +
                       esc(prompt) +
                       "\","
                       "\"stream\":false}";
    auto res = cli.Post("/api/generate", body, "application/json");
    if (!res || res->status != 200)
      return "ERROR: Ollama unavailable. Run: ollama serve";
    return parseResponse(res->body);
  }
};
struct DocItem {
  int id;
  string title;
  string text;
  vector<float> emb;
};

class DocumentDB {
  unordered_map<int, DocItem> store;
  HNSW hnsw;
  BruteForce bf;
  mutex mu;
  int nextId = 1;
  int dims = 0;

public:
  DocumentDB() : hnsw(16, 200) {}
  int insert(const string &title, const string &text,
             const vector<float> &emb) {
    lock_guard<mutex> lk(mu);
    if (dims == 0)
      dims = (int)emb.size();
    DocItem item{nextId++, title, text, emb};
    store[item.id] = item;
    VectorItem vi{item.id, title, "doc", emb};
    hnsw.insert(vi, cosine);
    bf.insert(vi);
    return item.id;
  }
  vector<pair<float, DocItem>> search(const vector<float> &q,
                                                int k, float max_dist = 0.7f) {
    lock_guard<mutex> lk(mu);
    if (store.empty())
      return {};
    auto raw =
        (store.size() < 10) ? bf.knn(q, k, cosine) : hnsw.knn(q, k, 50, cosine);
    vector<pair<float, DocItem>> out;
    for (auto &[d, id] : raw)
      if (store.count(id) && d <= max_dist)
        out.push_back({d, store[id]});
    return out;
  }
  bool remove(int id) {
    lock_guard<mutex> lk(mu);
    if (!store.count(id))
      return false;
    store.erase(id);
    hnsw.remove(id);
    bf.remove(id);
    return true;
  }
  vector<DocItem> all() {
    lock_guard<mutex> lk(mu);
    vector<DocItem> r;
    for (auto &[id, v] : store)
      r.push_back(v);
    return r;
  }
  size_t size() {
    lock_guard<mutex> lk(mu);
    return store.size();
  }
  int getDims() { return dims; }
};
void loadDemo(VectorDB &db) {
  auto dist = getDistFn("cosine");
  db.insert("Linked List: nodes connected by pointers", "cs",
            {0.90f, 0.85f, 0.72f, 0.68f, 0.12f, 0.08f, 0.15f, 0.10f, 0.05f,
             0.08f, 0.06f, 0.09f, 0.07f, 0.11f, 0.08f, 0.06f},
            dist);
  db.insert("Binary Search Tree: O(log n) search and insert", "cs",
            {0.88f, 0.82f, 0.78f, 0.74f, 0.15f, 0.10f, 0.08f, 0.12f, 0.06f,
             0.07f, 0.08f, 0.05f, 0.09f, 0.06f, 0.07f, 0.10f},
            dist);
  db.insert("Dynamic Programming: memoization overlapping subproblems", "cs",
            {0.82f, 0.76f, 0.88f, 0.80f, 0.20f, 0.18f, 0.12f, 0.09f, 0.07f,
             0.06f, 0.08f, 0.07f, 0.08f, 0.09f, 0.06f, 0.07f},
            dist);
  db.insert("Graph BFS and DFS: breadth and depth first traversal", "cs",
            {0.85f, 0.80f, 0.75f, 0.82f, 0.18f, 0.14f, 0.10f, 0.08f, 0.06f,
             0.09f, 0.07f, 0.06f, 0.10f, 0.08f, 0.09f, 0.07f},
            dist);
  db.insert("Hash Table: O(1) lookup with collision chaining", "cs",
            {0.87f, 0.78f, 0.70f, 0.76f, 0.13f, 0.11f, 0.09f, 0.14f, 0.08f,
             0.07f, 0.06f, 0.08f, 0.07f, 0.10f, 0.08f, 0.09f},
            dist);
  db.insert("Calculus: derivatives integrals and limits", "math",
            {0.12f, 0.15f, 0.18f, 0.10f, 0.91f, 0.86f, 0.78f, 0.72f, 0.08f,
             0.06f, 0.07f, 0.09f, 0.07f, 0.08f, 0.06f, 0.10f},
            dist);
  db.insert("Linear Algebra: matrices eigenvalues eigenvectors", "math",
            {0.20f, 0.18f, 0.15f, 0.12f, 0.88f, 0.90f, 0.82f, 0.76f, 0.09f,
             0.07f, 0.08f, 0.06f, 0.10f, 0.07f, 0.08f, 0.09f},
            dist);
  db.insert("Probability: distributions random variables Bayes theorem", "math",
            {0.15f, 0.12f, 0.20f, 0.18f, 0.84f, 0.80f, 0.88f, 0.82f, 0.07f,
             0.08f, 0.06f, 0.10f, 0.09f, 0.06f, 0.09f, 0.08f},
            dist);
  db.insert("Number Theory: primes modular arithmetic RSA cryptography", "math",
            {0.22f, 0.16f, 0.14f, 0.20f, 0.80f, 0.85f, 0.76f, 0.90f, 0.08f,
             0.09f, 0.07f, 0.06f, 0.08f, 0.10f, 0.07f, 0.06f},
            dist);
  db.insert("Combinatorics: permutations combinations generating functions",
            "math",
            {0.18f, 0.20f, 0.16f, 0.14f, 0.86f, 0.78f, 0.84f, 0.80f, 0.06f,
             0.07f, 0.09f, 0.08f, 0.06f, 0.09f, 0.10f, 0.07f},
            dist);
  db.insert("Neapolitan Pizza: wood-fired dough San Marzano tomatoes", "food",
            {0.08f, 0.06f, 0.09f, 0.07f, 0.07f, 0.08f, 0.06f, 0.09f, 0.90f,
             0.86f, 0.78f, 0.72f, 0.08f, 0.06f, 0.09f, 0.07f},
            dist);
  db.insert("Sushi: vinegared rice raw fish and nori rolls", "food",
            {0.06f, 0.08f, 0.07f, 0.09f, 0.09f, 0.06f, 0.08f, 0.07f, 0.86f,
             0.90f, 0.82f, 0.76f, 0.07f, 0.09f, 0.06f, 0.08f},
            dist);
  db.insert("Ramen: noodle soup with chashu pork and soft-boiled eggs", "food",
            {0.09f, 0.07f, 0.06f, 0.08f, 0.08f, 0.09f, 0.07f, 0.06f, 0.82f,
             0.78f, 0.90f, 0.84f, 0.09f, 0.07f, 0.08f, 0.06f},
            dist);
  db.insert("Tacos: corn tortillas with carnitas salsa and cilantro", "food",
            {0.07f, 0.09f, 0.08f, 0.06f, 0.06f, 0.07f, 0.09f, 0.08f, 0.78f,
             0.82f, 0.86f, 0.90f, 0.06f, 0.08f, 0.07f, 0.09f},
            dist);
  db.insert("Croissant: laminated pastry with buttery flaky layers", "food",
            {0.06f, 0.07f, 0.10f, 0.09f, 0.10f, 0.06f, 0.07f, 0.10f, 0.85f,
             0.80f, 0.76f, 0.82f, 0.09f, 0.07f, 0.10f, 0.06f},
            dist);
  db.insert("Basketball: fast-paced shooting dribbling slam dunks", "sports",
            {0.09f, 0.07f, 0.08f, 0.10f, 0.08f, 0.09f, 0.07f, 0.06f, 0.08f,
             0.07f, 0.09f, 0.06f, 0.91f, 0.85f, 0.78f, 0.72f},
            dist);
  db.insert("Football: tackles touchdowns field goals and strategy", "sports",
            {0.07f, 0.09f, 0.06f, 0.08f, 0.09f, 0.07f, 0.10f, 0.08f, 0.07f,
             0.09f, 0.08f, 0.07f, 0.87f, 0.89f, 0.82f, 0.76f},
            dist);
  db.insert("Tennis: racket volleys groundstrokes and Wimbledon serves",
            "sports",
            {0.08f, 0.06f, 0.09f, 0.07f, 0.07f, 0.08f, 0.06f, 0.09f, 0.09f,
             0.06f, 0.07f, 0.08f, 0.83f, 0.80f, 0.88f, 0.82f},
            dist);
  db.insert("Chess: openings endgames tactics strategic board game", "sports",
            {0.25f, 0.20f, 0.22f, 0.18f, 0.22f, 0.18f, 0.20f, 0.15f, 0.06f,
             0.08f, 0.07f, 0.09f, 0.80f, 0.84f, 0.78f, 0.90f},
            dist);
  db.insert("Swimming: butterfly freestyle backstroke Olympic competition",
            "sports",
            {0.06f, 0.08f, 0.07f, 0.09f, 0.08f, 0.06f, 0.09f, 0.07f, 0.10f,
             0.08f, 0.06f, 0.07f, 0.85f, 0.82f, 0.86f, 0.80f},
            dist);
}
int main() {
  VectorDB db(DIMS);
  DocumentDB docDB;
  OllamaClient ollama;
  loadDemo(db);
  bool ollamaUp = ollama.isAvailable();
  cout << "=== VectorDB Engine ===" << endl;
  cout << "http://localhost:8080" << endl;
  cout << db.size() << " demo vectors | " << DIMS
            << " dims | HNSW+KD-Tree+BruteForce" << endl;
  cout << "Ollama: "
            << (ollamaUp ? "ONLINE" : "OFFLINE (install from ollama.com)")
            << endl;
  if (ollamaUp)
    cout << "  embed model: " << ollama.embedModel
              << "  gen model: " << ollama.genModel << endl;
  httplib::Server svr;
  svr.Options(".*", [](const httplib::Request &, httplib::Response &res) {
    cors(res);
    res.status = 204;
  });
  svr.Get("/search", [&](const httplib::Request &req, httplib::Response &res) {
    cors(res);
    auto q = parseVec(req.get_param_value("v"));
    if ((int)q.size() != DIMS) {
      res.set_content("{\"error\":\"need " + to_string(DIMS) +
                          "D vector\"}",
                      "application/json");
      return;
    }
    int k = 5;
    try {
      k = stoi(req.get_param_value("k"));
    } catch (...) {
    }
    auto metric = req.get_param_value("metric");
    if (metric.empty())
      metric = "cosine";
    auto algo = req.get_param_value("algo");
    if (algo.empty())
      algo = "hnsw";
    auto out = db.search(q, k, metric, algo);
    ostringstream ss;
    ss << "{\"results\":[";
    for (size_t i = 0; i < out.hits.size(); i++) {
      if (i)
        ss << ',';
      auto &h = out.hits[i];
      ss << "{\"id\":" << h.id << ",\"metadata\":" << jS(h.meta)
         << ",\"category\":" << jS(h.cat) << ",\"distance\":" << fixed
         << setprecision(6) << h.dist << ",\"embedding\":" << jVec(h.emb)
         << '}';
    }
    ss << "],\"latencyUs\":" << out.us << ",\"algo\":" << jS(out.algo)
       << ",\"metric\":" << jS(out.metric) << '}';
    res.set_content(ss.str(), "application/json");
  });
  svr.Post("/insert", [&](const httplib::Request &req, httplib::Response &res) {
    cors(res);
    string meta, cat;
    vector<float> emb;
    if (!parseBody(req.body, meta, cat, emb) || (int)emb.size() != DIMS) {
      res.set_content("{\"error\":\"invalid body\"}", "application/json");
      return;
    }
    int id = db.insert(meta, cat, emb, getDistFn("cosine"));
    res.set_content("{\"id\":" + to_string(id) + "}", "application/json");
  });
  svr.Delete(R"(/delete/(\d+))", [&](const httplib::Request &req,
                                     httplib::Response &res) {
    cors(res);
    int id = stoi(req.matches[1]);
    bool ok = db.remove(id);
    res.set_content("{\"ok\":" + string(ok ? "true" : "false") + "}",
                    "application/json");
  });
  svr.Get("/items", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    auto items = db.all();
    ostringstream ss;
    ss << '[';
    for (size_t i = 0; i < items.size(); i++) {
      if (i)
        ss << ',';
      auto &v = items[i];
      ss << "{\"id\":" << v.id << ",\"metadata\":" << jS(v.metadata)
         << ",\"category\":" << jS(v.category)
         << ",\"embedding\":" << jVec(v.emb) << '}';
    }
    ss << ']';
    res.set_content(ss.str(), "application/json");
  });
  svr.Get("/benchmark",
          [&](const httplib::Request &req, httplib::Response &res) {
            cors(res);
            auto q = parseVec(req.get_param_value("v"));
            if ((int)q.size() != DIMS) {
              res.set_content("{\"error\":\"need " + to_string(DIMS) +
                                  "D vector\"}",
                              "application/json");
              return;
            }
            int k = 5;
            try {
              k = stoi(req.get_param_value("k"));
            } catch (...) {
            }
            auto metric = req.get_param_value("metric");
            if (metric.empty())
              metric = "cosine";
            auto b = db.benchmark(q, k, metric);
            ostringstream ss;
            ss << "{\"bruteforceUs\":" << b.bfUs << ",\"kdtreeUs\":" << b.kdUs
               << ",\"hnswUs\":" << b.hnswUs << ",\"itemCount\":" << b.n << '}';
            res.set_content(ss.str(), "application/json");
          });
  svr.Get("/hnsw-info", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    auto gi = db.hnswInfo();
    ostringstream ss;
    ss << "{\"topLayer\":" << gi.topLayer << ",\"nodeCount\":" << gi.nodeCount
       << ",\"nodesPerLayer\":[";
    for (size_t i = 0; i < gi.nodesPerLayer.size(); i++) {
      if (i)
        ss << ',';
      ss << gi.nodesPerLayer[i];
    }
    ss << "],\"edgesPerLayer\":[";
    for (size_t i = 0; i < gi.edgesPerLayer.size(); i++) {
      if (i)
        ss << ',';
      ss << gi.edgesPerLayer[i];
    }
    ss << "],\"nodes\":[";
    for (size_t i = 0; i < gi.nodes.size(); i++) {
      if (i)
        ss << ',';
      auto &n = gi.nodes[i];
      ss << "{\"id\":" << n.id << ",\"metadata\":" << jS(n.metadata)
         << ",\"category\":" << jS(n.category) << ",\"maxLyr\":" << n.maxLyr
         << '}';
    }
    ss << "],\"edges\":[";
    for (size_t i = 0; i < gi.edges.size(); i++) {
      if (i)
        ss << ',';
      auto &e = gi.edges[i];
      ss << "{\"src\":" << e.src << ",\"dst\":" << e.dst << ",\"lyr\":" << e.lyr
         << '}';
    }
    ss << "]}";
    res.set_content(ss.str(), "application/json");
  });
  svr.Post(
      "/doc/insert", [&](const httplib::Request &req, httplib::Response &res) {
        cors(res);
        auto title = extractStr(req.body, "title");
        auto text = extractStr(req.body, "text");
        if (title.empty() || text.empty()) {
          res.set_content("{\"error\":\"need title and text\"}",
                          "application/json");
          return;
        }
        auto chunks = chunkText(text, 250, 30);
        vector<int> ids;
        for (int i = 0; i < (int)chunks.size(); i++) {
          auto emb = ollama.embed(chunks[i]);
          if (emb.empty()) {
            res.set_content(
                "{\"error\":\"Ollama unavailable. "
                "Install from https://ollama.com then run: "
                "ollama pull nomic-embed-text && ollama pull llama3.2:1b\"}",
                "application/json");
            return;
          }
          string chunkTitle =
              (chunks.size() > 1) ? title + " [" + to_string(i + 1) + "/" +
                                        to_string(chunks.size()) + "]"
                                  : title;
          ids.push_back(docDB.insert(chunkTitle, chunks[i], emb));
        }
        ostringstream ss;
        ss << "{\"ids\":[";
        for (size_t i = 0; i < ids.size(); i++) {
          if (i)
            ss << ',';
          ss << ids[i];
        }
        ss << "],\"chunks\":" << chunks.size()
           << ",\"dims\":" << docDB.getDims() << '}';
        res.set_content(ss.str(), "application/json");
      });
  svr.Delete(R"(/doc/delete/(\d+))", [&](const httplib::Request &req,
                                         httplib::Response &res) {
    cors(res);
    int id = stoi(req.matches[1]);
    bool ok = docDB.remove(id);
    res.set_content("{\"ok\":" + string(ok ? "true" : "false") + "}",
                    "application/json");
  });
  svr.Get("/doc/list", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    auto docs = docDB.all();
    ostringstream ss;
    ss << '[';
    for (size_t i = 0; i < docs.size(); i++) {
      if (i)
        ss << ',';
      string preview = docs[i].text.substr(0, 120);
      if (docs[i].text.size() > 120)
        preview += "…";
      ss << "{\"id\":" << docs[i].id << ",\"title\":" << jS(docs[i].title)
         << ",\"preview\":" << jS(preview) << ",\"words\":"
         << (int)count(docs[i].text.begin(), docs[i].text.end(), ' ') + 1
         << '}';
    }
    ss << ']';
    res.set_content(ss.str(), "application/json");
  });
  svr.Post("/doc/search", [&](const httplib::Request &req,
                              httplib::Response &res) {
    cors(res);
    auto question = extractStr(req.body, "question");
    int k = extractInt(req.body, "k", 3);
    if (question.empty()) {
      res.set_content("{\"error\":\"need question\"}", "application/json");
      return;
    }
    auto qEmb = ollama.embed(question);
    if (qEmb.empty()) {
      res.set_content("{\"error\":\"Ollama unavailable\"}", "application/json");
      return;
    }
    auto hits = docDB.search(qEmb, k);
    ostringstream ss;
    ss << "{\"contexts\":[";
    for (size_t i = 0; i < hits.size(); i++) {
      if (i)
        ss << ',';
      ss << "{\"id\":" << hits[i].second.id
         << ",\"title\":" << jS(hits[i].second.title)
         << ",\"distance\":" << fixed << setprecision(4)
         << hits[i].first << '}';
    }
    ss << "]}";
    res.set_content(ss.str(), "application/json");
  });
  svr.Post("/doc/ask", [&](const httplib::Request &req,
                           httplib::Response &res) {
    cors(res);
    auto question = extractStr(req.body, "question");
    int k = extractInt(req.body, "k", 3);
    if (question.empty()) {
      res.set_content("{\"error\":\"need question\"}", "application/json");
      return;
    }
    auto qEmb = ollama.embed(question);
    if (qEmb.empty()) {
      res.set_content("{\"error\":\"Ollama unavailable\"}", "application/json");
      return;
    }
    auto hits = docDB.search(qEmb, k);
    ostringstream ctx;
    for (int i = 0; i < (int)hits.size(); i++) {
      ctx << "[" << (i + 1) << "] " << hits[i].second.title << ":\n"
          << hits[i].second.text << "\n\n";
    }
    string prompt =
        "You are a helpful assistant. Answer the user's question directly. "
        "Use the provided context if it contains relevant information. "
        "If it doesn't, just use your own general knowledge. "
        "IMPORTANT: Do NOT mention the 'context', 'provided text', or say "
        "things like 'the context doesn't mention'. "
        "Just answer the question naturally.\n\n"
        "Context:\n" +
        ctx.str() + "Question: " + question +
        "\n\n"
        "Answer:";
    auto answer = ollama.generate(prompt);
    ostringstream ss;
    ss << "{\"answer\":" << jS(answer) << ",\"model\":" << jS(ollama.genModel)
       << ",\"contexts\":[";
    for (size_t i = 0; i < hits.size(); i++) {
      if (i)
        ss << ',';
      ss << "{\"id\":" << hits[i].second.id
         << ",\"title\":" << jS(hits[i].second.title)
         << ",\"text\":" << jS(hits[i].second.text)
         << ",\"distance\":" << fixed << setprecision(4)
         << hits[i].first << '}';
    }
    ss << "],\"docCount\":" << docDB.size() << '}';
    res.set_content(ss.str(), "application/json");
  });
  svr.Get("/status", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    bool up = ollama.isAvailable();
    ostringstream ss;
    ss << "{\"ollamaAvailable\":" << (up ? "true" : "false")
       << ",\"embedModel\":" << jS(ollama.embedModel)
       << ",\"genModel\":" << jS(ollama.genModel)
       << ",\"docCount\":" << docDB.size() << ",\"docDims\":" << docDB.getDims()
       << ",\"demoDims\":" << DIMS << ",\"demoCount\":" << db.size() << '}';
    res.set_content(ss.str(), "application/json");
  });
  svr.Get("/stats", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    ostringstream ss;
    ss << "{\"count\":" << db.size() << ",\"dims\":" << DIMS
       << ",\"algorithms\":[\"bruteforce\",\"kdtree\",\"hnsw\"]"
       << ",\"metrics\":[\"euclidean\",\"cosine\",\"manhattan\"]}";
    res.set_content(ss.str(), "application/json");
  });
  svr.Get("/", [](const httplib::Request &, httplib::Response &res) {
    ifstream f("index.html");
    if (!f.is_open()) {
      res.status = 404;
      return;
    }
    res.set_content(string(istreambuf_iterator<char>(f),
                                istreambuf_iterator<char>()),
                    "text/html");
  });
  svr.listen("127.0.0.1", 8080);
  return 0;
}

