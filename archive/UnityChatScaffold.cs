// Unity C# script scaffold for connecting to SENTIENX /api/chat endpoint
// Attach this script to your chat UI manager or character controller
using UnityEngine;
using UnityEngine.Networking;
using System.Collections;

public class UnitySentienxChat : MonoBehaviour
{
    // Call this method with the user's message
    public void SendMessageToSentienx(string userMessage)
    {
        StartCoroutine(PostChatMessage(userMessage));
    }

    IEnumerator PostChatMessage(string message)
    {
        string url = "http://localhost:8080/api/chat";
        WWWForm form = new WWWForm();
        form.AddField("message", message);

        using (UnityWebRequest www = UnityWebRequest.Post(url, form))
        {
            yield return www.SendWebRequest();

            if (www.result == UnityWebRequest.Result.Success)
            {
                string response = www.downloadHandler.text;
                Debug.Log("SENTIENX reply: " + response);
                // TODO: Parse JSON and display reply in your UI/character
            }
            else
            {
                Debug.LogError("Error: " + www.error);
            }
        }
    }
}
