using System.Diagnostics;

namespace OrchAI.Bootstrap;

internal static class Program
{
    private const string DefaultApiHost = "127.0.0.1";
    private const string DefaultApiPort = "8000";

    public static int Main(string[] args)
    {
        BootstrapOptions options;
        try
        {
            options = BootstrapOptions.Parse(args);
        }
        catch (BootstrapException ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 1;
        }

        var exitCode = Run(options);
        if (options.PauseOnExit)
        {
            Console.WriteLine();
            Console.WriteLine("Press any key to close this window...");
            Console.ReadKey(intercept: true);
        }

        return exitCode;
    }

    private static int Run(BootstrapOptions options)
    {
        if (options.ShowHelp)
        {
            PrintHelp();
            return 0;
        }

        try
        {
            var rootDirectory = ResolveRepositoryRoot(options.RepositoryPath);
            if (rootDirectory is null)
            {
                Console.Error.WriteLine("[error] Could not locate the OrchAI repository root.");
                Console.Error.WriteLine("        Run this executable from the repository or pass --repo <path>.");
                return 1;
            }

            var paths = BootstrapPaths.FromRoot(rootDirectory);
            ValidateRequiredPaths(paths);

            Console.WriteLine("OrchAI Windows bootstrap");
            Console.WriteLine($"Repository: {paths.RootDirectory}");
            Console.WriteLine($"Mode:       {ToModeArgument(options.Mode)}");
            Console.WriteLine();

            ValidatePrerequisites(options.Mode);

            if (options.StatusOnly)
            {
                return RunLauncherStep("Check local process status", paths.ControlLauncher, "status");
            }

            var setupModeArgument = ToSetupModeArgument(options.Mode);
            var checkExitCode = RunLauncherStep("Run setup checks", paths.SetupLauncher, $"check {setupModeArgument}");
            if (checkExitCode != 0)
            {
                return checkExitCode;
            }

            if (options.CheckOnly)
            {
                Console.WriteLine();
                Console.WriteLine("[ok] OrchAI checks completed.");
                return 0;
            }

            var startExitCode = RunLauncherStep("Start OrchAI", paths.ControlLauncher, $"start {ToModeArgument(options.Mode)}");
            if (startExitCode != 0)
            {
                return startExitCode;
            }

            var statusExitCode = RunLauncherStep("Check local process status", paths.ControlLauncher, "status");
            if (statusExitCode != 0)
            {
                return statusExitCode;
            }

            if (options.Mode == BootstrapMode.Api)
            {
                var apiUrl = ResolveApiDocsUrl(paths.RootDirectory);
                if (!options.NoBrowser)
                {
                    OpenBrowser(apiUrl);
                }

                Console.WriteLine();
                Console.WriteLine($"[ok] OrchAI API is ready at {apiUrl}");
            }
            else
            {
                Console.WriteLine();
                Console.WriteLine("[ok] OrchAI Desktop is starting -- its own window will open shortly.");
            }

            return 0;
        }
        catch (BootstrapException ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 1;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("[error] Unexpected bootstrap failure.");
            Console.Error.WriteLine($"        {ex.Message}");
            return 1;
        }
    }

    private static DirectoryInfo? ResolveRepositoryRoot(string? requestedPath)
    {
        var candidates = new List<DirectoryInfo>();

        if (!string.IsNullOrWhiteSpace(requestedPath))
        {
            candidates.Add(new DirectoryInfo(Path.GetFullPath(requestedPath)));
        }

        candidates.Add(new DirectoryInfo(Environment.CurrentDirectory));
        candidates.Add(new DirectoryInfo(AppContext.BaseDirectory));

        foreach (var candidate in candidates)
        {
            var current = candidate;
            while (current is not null)
            {
                if (File.Exists(Path.Combine(current.FullName, "orchai.bat")))
                {
                    return current;
                }

                current = current.Parent;
            }
        }

        return null;
    }

    private static void ValidateRequiredPaths(BootstrapPaths paths)
    {
        RequireFile(paths.MainLauncher, "repository root launcher");
        RequireFile(paths.SetupLauncher, "setup launcher");
        RequireFile(paths.ControlLauncher, "control launcher");
    }

    private static void RequireFile(string path, string label)
    {
        if (File.Exists(path))
        {
            return;
        }

        throw new BootstrapException($"[error] Missing {label}: {path}");
    }

    // Node.js is only required for Desktop mode (it builds
    // apps/desktop/frontend) -- headless API-only use never needs it,
    // mirroring tools/windows/orchai-setup.bat's own Node.js scoping.
    private static void ValidatePrerequisites(BootstrapMode mode)
    {
        Console.WriteLine("Checking required local tools...");

        var missingTools = new List<string>();
        CheckTool("uv", "Install uv from https://docs.astral.sh/uv/", missingTools);
        if (mode == BootstrapMode.Desktop)
        {
            CheckTool("node", "Install Node.js from https://nodejs.org/", missingTools);
        }

        if (missingTools.Count > 0)
        {
            Console.WriteLine();
            Console.Error.WriteLine("[error] One or more required tools are missing.");
            Console.Error.WriteLine("        Install them first, then re-run this bootstrap.");
            throw new BootstrapException("[error] Prerequisite validation failed.");
        }

        Console.WriteLine("[ok] All required tools were found.");
    }

    private static void CheckTool(string toolName, string guidance, ICollection<string> missingTools)
    {
        var result = RunProcess("where.exe", toolName, Environment.CurrentDirectory, echoCommand: false);
        if (result.ExitCode == 0)
        {
            Console.WriteLine($"[ok] {toolName}");
            return;
        }

        Console.WriteLine($"[missing] {toolName}");
        Console.WriteLine($"          {guidance}");
        missingTools.Add(toolName);
    }

    // tools/windows/orchai-setup.bat's `check` argument uses
    // "headless"/"desktop" vocabulary (what to prepare the environment
    // for), while orchai-control.bat's `start` uses "api"/"desktop"
    // (what process to actually run) -- both scripts already shipped
    // with those distinct vocabularies, so the bootstrap translates
    // between them rather than introducing a third one.
    private static string ToSetupModeArgument(BootstrapMode mode) =>
        mode == BootstrapMode.Api ? "headless" : "desktop";

    private static string ToModeArgument(BootstrapMode mode) =>
        mode == BootstrapMode.Api ? "api" : "desktop";

    private static int RunLauncherStep(string label, string launcherPath, string argument)
    {
        Console.WriteLine();
        Console.WriteLine($"==> {label}");
        Console.WriteLine($"    call \"{launcherPath}\" {argument}");

        var result = RunProcess("cmd.exe", $"/d /c call \"{launcherPath}\" {argument}", Path.GetDirectoryName(launcherPath)!);
        if (result.ExitCode != 0)
        {
            Console.Error.WriteLine();
            Console.Error.WriteLine($"[error] Failed step: {label}");
            Console.Error.WriteLine($"        Command: call \"{launcherPath}\" {argument}");
            Console.Error.WriteLine($"        Exit code: {result.ExitCode}");
        }

        return result.ExitCode;
    }

    private static ProcessResult RunProcess(
        string fileName,
        string arguments,
        string workingDirectory,
        bool echoCommand = true)
    {
        if (echoCommand)
        {
            Console.WriteLine($"    {fileName} {arguments}");
        }

        using var process = new Process();
        process.StartInfo = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            WorkingDirectory = workingDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        process.OutputDataReceived += (_, eventArgs) =>
        {
            if (echoCommand && eventArgs.Data is not null)
            {
                Console.WriteLine(eventArgs.Data);
            }
        };
        process.ErrorDataReceived += (_, eventArgs) =>
        {
            if (echoCommand && eventArgs.Data is not null)
            {
                Console.Error.WriteLine(eventArgs.Data);
            }
        };

        process.Start();
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        process.WaitForExit();

        return new ProcessResult(process.ExitCode);
    }

    private static string ResolveApiDocsUrl(string rootDirectory)
    {
        var envValues = ReadEnvFile(Path.Combine(rootDirectory, ".env"));

        var host = GetConfiguredValue("ORCHAI_API_HOST", envValues);
        if (string.IsNullOrWhiteSpace(host))
        {
            host = DefaultApiHost;
        }

        var port = GetConfiguredValue("ORCHAI_API_PORT", envValues);
        if (string.IsNullOrWhiteSpace(port))
        {
            port = DefaultApiPort;
        }

        return $"http://{host.Trim()}:{port.Trim()}/docs";
    }

    private static string? GetConfiguredValue(string key, IReadOnlyDictionary<string, string> envValues)
    {
        var processValue = Environment.GetEnvironmentVariable(key);
        if (!string.IsNullOrWhiteSpace(processValue))
        {
            return processValue;
        }

        return envValues.TryGetValue(key, out var fileValue) ? fileValue : null;
    }

    private static Dictionary<string, string> ReadEnvFile(string path)
    {
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!File.Exists(path))
        {
            return values;
        }

        foreach (var rawLine in File.ReadLines(path))
        {
            var line = rawLine.Trim();
            if (line.Length == 0 || line.StartsWith("#", StringComparison.Ordinal))
            {
                continue;
            }

            var separatorIndex = line.IndexOf('=');
            if (separatorIndex <= 0)
            {
                continue;
            }

            var key = line[..separatorIndex].Trim();
            var value = line[(separatorIndex + 1)..].Trim().Trim('"');
            values[key] = value;
        }

        return values;
    }

    private static void OpenBrowser(string webUrl)
    {
        Console.WriteLine();
        Console.WriteLine($"Opening OrchAI at {webUrl}");

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = webUrl,
                UseShellExecute = true,
            });
        }
        catch (Exception ex)
        {
            throw new BootstrapException($"[error] Could not open the browser for {webUrl}: {ex.Message}");
        }
    }

    private static void PrintHelp()
    {
        Console.WriteLine("OrchAI Windows bootstrap");
        Console.WriteLine();
        Console.WriteLine("Usage:");
        Console.WriteLine(
            "  orchai-bootstrap.exe [--repo <path>] [--mode api|desktop] [--check-only] [--status] [--no-browser] [--pause-on-exit]");
        Console.WriteLine();
        Console.WriteLine("Options:");
        Console.WriteLine("  --repo <path>   Use a specific OrchAI repository root.");
        Console.WriteLine("  --mode <mode>   Start mode: api (headless) or desktop. Defaults to desktop.");
        Console.WriteLine("  --check-only    Run prerequisite and setup checks without startup.");
        Console.WriteLine("  --status        Show local process status only.");
        Console.WriteLine("  --no-browser    Start OrchAI without opening the browser (api mode only).");
        Console.WriteLine("  --pause-on-exit Keep the window open until a key is pressed.");
        Console.WriteLine("  --help          Show this help.");
    }
}

internal enum BootstrapMode
{
    Api,
    Desktop,
}

internal sealed record BootstrapPaths(string RootDirectory, string MainLauncher, string SetupLauncher, string ControlLauncher)
{
    public static BootstrapPaths FromRoot(DirectoryInfo rootDirectory)
    {
        var toolsDirectory = Path.Combine(rootDirectory.FullName, "tools", "windows");
        return new BootstrapPaths(
            rootDirectory.FullName,
            Path.Combine(rootDirectory.FullName, "orchai.bat"),
            Path.Combine(toolsDirectory, "orchai-setup.bat"),
            Path.Combine(toolsDirectory, "orchai-control.bat"));
    }
}

internal sealed record BootstrapOptions(
    string? RepositoryPath,
    BootstrapMode Mode,
    bool CheckOnly,
    bool StatusOnly,
    bool NoBrowser,
    bool PauseOnExit,
    bool ShowHelp)
{
    public static BootstrapOptions Parse(string[] args)
    {
        string? repositoryPath = null;
        var mode = BootstrapMode.Desktop;
        var checkOnly = false;
        var statusOnly = false;
        var noBrowser = false;
        var pauseOnExit = false;
        var showHelp = false;

        for (var index = 0; index < args.Length; index++)
        {
            var current = args[index];
            if (string.Equals(current, "--repo", StringComparison.OrdinalIgnoreCase))
            {
                if (index + 1 >= args.Length)
                {
                    throw new BootstrapException("[error] Missing value for --repo.");
                }

                repositoryPath = args[++index];
            }
            else if (string.Equals(current, "--mode", StringComparison.OrdinalIgnoreCase))
            {
                if (index + 1 >= args.Length)
                {
                    throw new BootstrapException("[error] Missing value for --mode.");
                }

                var modeValue = args[++index];
                if (string.Equals(modeValue, "api", StringComparison.OrdinalIgnoreCase))
                {
                    mode = BootstrapMode.Api;
                }
                else if (string.Equals(modeValue, "desktop", StringComparison.OrdinalIgnoreCase))
                {
                    mode = BootstrapMode.Desktop;
                }
                else
                {
                    throw new BootstrapException($"[error] Unknown --mode value: {modeValue} (expected api or desktop).");
                }
            }
            else if (string.Equals(current, "--check-only", StringComparison.OrdinalIgnoreCase))
            {
                checkOnly = true;
            }
            else if (string.Equals(current, "--status", StringComparison.OrdinalIgnoreCase))
            {
                statusOnly = true;
            }
            else if (string.Equals(current, "--no-browser", StringComparison.OrdinalIgnoreCase))
            {
                noBrowser = true;
            }
            else if (string.Equals(current, "--pause-on-exit", StringComparison.OrdinalIgnoreCase))
            {
                pauseOnExit = true;
            }
            else if (
                string.Equals(current, "--help", StringComparison.OrdinalIgnoreCase)
                || string.Equals(current, "-h", StringComparison.OrdinalIgnoreCase)
                || string.Equals(current, "/?", StringComparison.OrdinalIgnoreCase))
            {
                showHelp = true;
            }
            else
            {
                throw new BootstrapException($"[error] Unknown option: {current}");
            }
        }

        return new BootstrapOptions(repositoryPath, mode, checkOnly, statusOnly, noBrowser, pauseOnExit, showHelp);
    }
}

internal sealed record ProcessResult(int ExitCode);

internal sealed class BootstrapException : Exception
{
    public BootstrapException(string message) : base(message)
    {
    }
}
