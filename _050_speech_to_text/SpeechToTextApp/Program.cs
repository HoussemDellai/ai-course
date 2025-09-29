using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;
using System.Threading.Tasks;
using System.IO;

namespace TextToSpeech
{
    class Program
    {
        static async Task Main()
        {
            await SynthesizeAudioAsync();
        }

        static async Task SynthesizeAudioAsync()
        {
            var config = SpeechConfig.FromSubscription("<REPLACE BY CONGNITIVE SERVICES KEY>", "swedencentral");

            config.SpeechSynthesisVoiceName = "zh-CN-XiaochenMultilingualNeural";
            // config.SpeechSynthesisVoiceName = "fr-FR-VivienneMultilingualNeural";
            // config.SpeechSynthesisVoiceName = "en-US-BrandonMultilingualNeural";

            // var audioConfig = AudioConfig.FromDefaultSpeakerOutput();
            var audioConfig = AudioConfig.FromWavFileOutput("D:/newsletter.wav");

            using var synthesizer = new SpeechSynthesizer(config, audioConfig);

            var text = File.ReadAllText("text.txt");

            await synthesizer.SpeakTextAsync(text);
        }
    }
}